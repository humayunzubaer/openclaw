#include "ps/engine.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <sstream>
#include <stdexcept>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <leptonica/allheaders.h>
#include <tesseract/baseapi.h>
#include <tesseract/resultiterator.h>

#include "imaging.hpp"
#include "tables.hpp"
#include "text.hpp"

namespace ps {

namespace {

// Glyph-cluster height the Tesseract LSTM models read best at, measured on
// the benchmark (clean 200-DPI pages with 12-13 pt text).
constexpr double kTargetTextHeight = 20.0;
constexpr int kPad = 12;

const char* kBengaliDigits = "০১২৩৪৫৬৭৮৯,./-:";
const char* kLatinDigits = "0123456789,./-:";

struct Word {
  std::string text;
  float conf = 0;
  cv::Rect box;
};

cv::Mat padWhite(const cv::Mat& gray, int pad) {
  cv::Mat out;
  cv::copyMakeBorder(gray, out, pad, pad, pad, pad, cv::BORDER_CONSTANT, cv::Scalar(255));
  return out;
}

std::string jsonEscape(const std::string& s) {
  std::string o;
  for (char c : s) {
    switch (c) {
      case '"': o += "\\\""; break;
      case '\\': o += "\\\\"; break;
      case '\n': o += "\\n"; break;
      case '\t': o += "\\t"; break;
      case '\r': break;
      default:
        if (static_cast<unsigned char>(c) < 0x20) continue;
        o += c;
    }
  }
  return o;
}

// Tokens made only of these are rule fragments, not text.
bool isJunkToken(const std::string& s) {
  for (char32_t c : text::decode(s)) {
    if (!(c == U'|' || c == U'<' || c == U'>' || c == U'[' || c == U']' || c == U'{' || c == U'}' ||
          c == U'_' || c == U'~' || c == U'`' || c == U'\\')) return false;
  }
  return true;
}

// Bounding box of the ink, ignoring specks (rule-crossing remnants, dust)
// that would otherwise stretch the crop to the cell corners.
cv::Rect inkBounds(const cv::Mat& ink, double minArea) {
  cv::Mat labels, stats, centroids;
  const int n = cv::connectedComponentsWithStats(ink, labels, stats, centroids, 8);
  cv::Rect box;
  for (int i = 1; i < n; ++i) {
    if (stats.at<int>(i, cv::CC_STAT_AREA) < minArea) continue;
    const cv::Rect r(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
                     stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
    box = box.area() ? (box | r) : r;
  }
  return box;
}

// A number never ends in a separator; a trailing ".", "," or "-" in a table
// cell is a speck or rule end read as punctuation.
std::string trimNumberTail(const std::string& s) {
  auto u = text::decode(s);
  if (!text::profile(s).numberLike()) return s;
  while (u.size() > 1 && text::isNumericPunct(u.back()) && u.back() != U'%') u.pop_back();
  return text::encode(u);
}

bool isNoise(const std::string& s) {
  // Rule remnants and specks read as punctuation-only strings.
  for (char32_t c : text::decode(s)) {
    if (c > 0x7F || std::isalnum(static_cast<int>(c))) return false;
  }
  return true;
}

}  // namespace

struct Engine::Impl {
  Options opt;
  tesseract::TessBaseAPI main;    // Bengali model (Options::languages), no restrictions
  tesseract::TessBaseAPI* primary = &main;  // model for this page: main or latin
  tesseract::TessBaseAPI digits;  // same model, whitelist set per call
  tesseract::TessBaseAPI latin;   // English model for words the Bengali model cannot read
  bool hasLatin = false;
  int debugIndex = 0;

  explicit Impl(Options o) : opt(std::move(o)) {
    setMsgSeverity(L_SEVERITY_NONE);  // Leptonica chatter on stderr is not actionable here
    const char* dir = opt.tessdataDir.empty() ? nullptr : opt.tessdataDir.c_str();
    if (main.Init(dir, opt.languages.c_str(), tesseract::OEM_LSTM_ONLY) != 0 ||
        digits.Init(dir, opt.languages.c_str(), tesseract::OEM_LSTM_ONLY) != 0) {
      throw std::runtime_error("Tesseract init failed: check tessdata dir and " + opt.languages + ".traineddata");
    }
    hasLatin = !opt.latinLanguage.empty() && latin.Init(dir, opt.latinLanguage.c_str(), tesseract::OEM_LSTM_ONLY) == 0;
    for (auto* api : {&main, &digits, &latin}) {
      api->SetVariable("debug_file", "/dev/null");
      api->SetVariable("user_defined_dpi", "300");
    }
  }

  cv::Mat cropWord(const cv::Mat& gray, const cv::Rect& box) {
    cv::Rect r(box.x - 4, box.y - 4, box.width + 8, box.height + 8);
    r &= cv::Rect(0, 0, gray.cols, gray.rows);
    return r.area() > 0 ? padWhite(gray(r), kPad) : cv::Mat();
  }

  Word readWith(tesseract::TessBaseAPI& api, const cv::Mat& crop, tesseract::PageSegMode psm, const Word& like) {
    Word w = like;
    api.SetPageSegMode(psm);
    setImage(api, crop);
    std::unique_ptr<char[]> t(api.GetUTF8Text());
    w.text = t ? text::trim(t.get()) : "";
    w.conf = static_cast<float>(api.MeanTextConf());
    return w;
  }

  // English words (LC No., Invoice, Bill of Entry) come out of the Bengali
  // model as junk with ASCII in it ("10-251612", "0000]"), often split into
  // pieces. Re-read each run of such words as one English phrase and keep it
  // when it is more confident and reads as clean Latin text.
  std::optional<Word> rereadLatinRun(const cv::Mat& gray, const std::vector<Word>& run) {
    if (!hasLatin || run.empty()) return std::nullopt;
    cv::Rect box = run.front().box;
    float conf = 0;
    for (auto& w : run) {
      box |= w.box;
      conf += w.conf;
    }
    conf /= run.size();
    const cv::Mat crop = cropWord(gray, box);
    if (crop.empty()) return std::nullopt;
    Word latinRead = readWith(latin, crop, tesseract::PSM_SINGLE_LINE, run.front());
    latinRead.box = box;
    int clean = 0, total = 0;
    for (char32_t c : text::decode(latinRead.text)) {
      if (c == U' ') continue;
      ++total;
      if (c < 0x80 && (std::isalnum(static_cast<int>(c)) || std::strchr(".,:;/()-#&%'", static_cast<char>(c)))) ++clean;
    }
    if (std::getenv("PS_TRACE")) std::fprintf(stderr, "latin: %.0f -> '%s' %.0f\n", conf, latinRead.text.c_str(), latinRead.conf);
    if (total == 0 || clean < 0.9 * total || latinRead.conf < 60 || latinRead.conf <= conf) return std::nullopt;
    return latinRead;
  }

  void dump(const char* name, const cv::Mat& img) {
    if (opt.debugDir.empty()) return;
    char path[512];
    std::snprintf(path, sizeof path, "%s/%02d-%s.png", opt.debugDir.c_str(), debugIndex++, name);
    cv::imwrite(path, img);
  }

  void setImage(tesseract::TessBaseAPI& api, const cv::Mat& gray) {
    api.SetImage(gray.data, gray.cols, gray.rows, 1, static_cast<int>(gray.step));
  }

  // Runs one Tesseract pass and returns words grouped into text lines.
  std::vector<std::vector<Word>> ocrLines(const cv::Mat& gray, tesseract::PageSegMode psm) {
    tesseract::TessBaseAPI& api = *primary;
    setImage(api, gray);
    api.SetPageSegMode(psm);
    std::vector<std::vector<Word>> lines;
    if (api.Recognize(nullptr) != 0) return lines;
    std::unique_ptr<tesseract::ResultIterator> it(api.GetIterator());
    if (!it) return lines;
    do {
      if (it->Empty(tesseract::RIL_WORD)) continue;
      if (lines.empty() || it->IsAtBeginningOf(tesseract::RIL_TEXTLINE)) lines.emplace_back();
      std::unique_ptr<char[]> t(it->GetUTF8Text(tesseract::RIL_WORD));
      if (!t) continue;
      Word w;
      w.text = text::trim(t.get());
      w.conf = it->Confidence(tesseract::RIL_WORD);
      int x1, y1, x2, y2;
      it->BoundingBox(tesseract::RIL_WORD, &x1, &y1, &x2, &y2);
      w.box = cv::Rect(x1, y1, x2 - x1, y2 - y1);
      if (!w.text.empty()) lines.back().push_back(std::move(w));
    } while (it->Next(tesseract::RIL_WORD));
    lines.erase(std::remove_if(lines.begin(), lines.end(), [](auto& l) { return l.empty(); }), lines.end());
    return lines;
  }

  // Refines one recognized line: English runs first, then number re-reads.
  std::vector<Word> refineLine(const cv::Mat& gray, const std::vector<Word>& words) {
    std::vector<Word> out;
    std::vector<Word> run;
    auto flushRun = [&]() {
      if (run.empty()) return;
      const bool allNumeric = std::all_of(run.begin(), run.end(), [](const Word& w) {
        const auto p = text::profile(w.text);
        return p.numberLike() && p.latin == 0;
      });
      std::optional<Word> latinRead;
      if (!allNumeric && primary != &latin) latinRead = rereadLatinRun(gray, run);
      if (latinRead) {
        out.push_back(*latinRead);
      } else {
        for (auto& w : run) out.push_back(rereadNumber(gray, w));
      }
      run.clear();
    };
    for (auto& w : words) {
      if (isJunkToken(w.text) && run.empty()) continue;
      if (text::profile(w.text).hasAscii || isJunkToken(w.text)) {
        run.push_back(w);
        continue;
      }
      flushRun();
      out.push_back(rereadNumber(gray, w));
    }
    flushRun();
    out.erase(std::remove_if(out.begin(), out.end(), [](const Word& w) { return isJunkToken(w.text); }), out.end());
    return out;
  }

  // Re-reads a number-like word with only digits and number punctuation
  // allowed, in the word's own digit script. Returns the better read.
  Word rereadNumber(const cv::Mat& gray, const Word& first) {
    const auto prof = text::profile(first.text);
    if (!opt.numericRereads || !prof.numberLike()) return first;
    const cv::Mat crop = cropWord(gray, first.box);
    if (crop.empty()) return first;
    // Bengali ৪ looks like Latin 8, ৭ like 9, ০ like 0: read the box in both
    // digit scripts and keep the more confident, preferring the first read's
    // script on near-ties.
    const bool preferBengali = prof.bengali >= prof.latin;
    Word best = first;
    for (bool bengali : {preferBengali, !preferBengali}) {
      const Word w = readDigits(crop, bengali, tesseract::PSM_SINGLE_WORD, first);
      if (w.text.empty() || w.text.find(' ') != std::string::npos) continue;
      const float margin = bengali == preferBengali ? 0.0f : 5.0f;
      if (w.conf >= best.conf + margin) best = w;
    }
    return best;
  }

  // Forces a digits-only read of a whole cell (column known to be numeric).
  std::optional<Word> readCellAsNumber(const cv::Mat& crop, bool bengali) {
    if (!opt.numericRereads) return std::nullopt;
    // Single-word mode: single-line mode drops lone glyphs like "২".
    const Word w = readDigits(crop, bengali, tesseract::PSM_SINGLE_WORD, Word{});
    if (std::getenv("PS_TRACE")) std::fprintf(stderr, "cell-as-number: '%s' %.0f\n", w.text.c_str(), w.conf);
    if (w.text.empty() || !text::profile(w.text).numberLike() || w.conf < 40) return std::nullopt;
    return w;
  }

  // In a column that is mostly numbers (serial no., quantity, amount), a short
  // non-numeric read is almost always a digit mistaken for a letter: Bengali
  // ৬ vs ঙ, ৪ vs 8, ৩ vs ও. Re-read those cells digits-only.
  void rereadNumericColumns(Block& table, const std::vector<cv::Mat>& crops) {
    for (int c = 0; c < table.cols; ++c) {
      // Short low-confidence reads are exactly the cells in question, so
      // they abstain from the vote.
      int voters = 0, numeric = 0, bengali = 0, latin = 0;
      for (auto& cell : table.cells) {
        if (cell.col != c || cell.text.empty()) continue;
        const auto p = text::profile(cell.text);
        const bool unsure = text::decode(cell.text).size() <= 3 && cell.confidence < 80;
        if (p.numberLike()) {
          ++numeric;
          ++voters;
          bengali += p.bengali;
          latin += p.latin;
        } else if (!unsure) {
          ++voters;
        }
      }
      if (numeric < 2 || numeric < 0.5 * voters) continue;
      for (size_t k = 0; k < table.cells.size(); ++k) {
        Cell& cell = table.cells[k];
        if (cell.col != c || cell.text.empty() || crops[k].empty()) continue;
        if (text::profile(cell.text).numberLike() || text::decode(cell.text).size() > 3) continue;
        if (auto w = readCellAsNumber(crops[k], bengali >= latin)) {
          cell.text = trimNumberTail(w->text);
          cell.confidence = w->conf;
        }
      }
    }
  }

  // Digits-only read. Bengali digits use the Bengali model; Latin digits the
  // English one when present (it knows Latin digit shapes far better).
  Word readDigits(const cv::Mat& crop, bool bengali, tesseract::PageSegMode psm, const Word& like) {
    tesseract::TessBaseAPI& api = bengali || !hasLatin ? digits : latin;
    api.SetVariable("tessedit_char_whitelist", bengali ? kBengaliDigits : kLatinDigits);
    Word w = readWith(api, crop, psm, like);
    if (&api == &latin) api.SetVariable("tessedit_char_whitelist", "");
    return w;
  }

  double probeConfidence(tesseract::TessBaseAPI& api, const cv::Mat& gray) {
    // Middle band of the page: enough text to judge, cheap to read.
    const cv::Rect band(gray.cols / 8, gray.rows / 3, gray.cols * 3 / 4, gray.rows / 4);
    setImage(api, gray(band));
    api.SetPageSegMode(tesseract::PSM_AUTO);
    std::unique_ptr<char[]> t(api.GetUTF8Text());
    return api.MeanTextConf();
  }
};

Engine::Engine(Options options) : impl_(std::make_unique<Impl>(std::move(options))) {}
Engine::~Engine() = default;

Page Engine::recognize(const cv::Mat& image) {
  Impl& I = *impl_;
  I.debugIndex = 0;
  Page page;

  // 1. Find the sheet and flatten perspective.
  cv::Mat gray = imaging::toGray(image);
  if (I.opt.detectPage) {
    if (auto quad = imaging::findPage(gray)) {
      gray = imaging::warpPage(gray, *quad);
      page.pageFound = true;
    }
  }
  I.dump("page", gray);

  // 2. Lighting, then orientation and script. Sideways is geometric; up vs
  // down and Bengali vs English are decided together by which model reads a
  // probe band most confidently.
  cv::Mat flat = imaging::flattenIllumination(gray);
  if (imaging::isSideways(imaging::binarize(flat))) flat = imaging::rotateQuarterTurns(flat, 1);
  {
    const double s = std::min(1.0, 1600.0 / flat.cols);
    cv::Mat probe;
    cv::resize(flat, probe, {}, s, s, cv::INTER_AREA);
    const cv::Mat flipped = imaging::rotateQuarterTurns(probe, 2);
    const double ben0 = I.probeConfidence(I.main, probe), ben180 = I.probeConfidence(I.main, flipped);
    double eng0 = -1, eng180 = -1;
    if (I.hasLatin) {
      eng0 = I.probeConfidence(I.latin, probe);
      eng180 = I.probeConfidence(I.latin, flipped);
    }
    // Bengali wins ties: the Bengali pipeline already rescues English words.
    const bool latinPage = std::max(eng0, eng180) > std::max(ben0, ben180) + 10;
    I.primary = latinPage ? &I.latin : &I.main;
    page.script = latinPage ? "latin" : "bengali";
    const double up = latinPage ? eng0 : ben0, down = latinPage ? eng180 : ben180;
    if (down > up + 10) flat = imaging::rotateQuarterTurns(flat, 2);
  }

  // 3. Deskew.
  page.skewDegrees = imaging::estimateSkew(imaging::binarize(flat));
  flat = imaging::rotate(flat, page.skewDegrees, 255);

  // 4. Bring text to the size the model reads best.
  cv::Mat ink = imaging::binarize(flat);
  const double textHeight = imaging::medianTextHeight(ink);
  if (textHeight > 0) {
    const double s = std::clamp(kTargetTextHeight / textHeight, 0.5, 3.0);
    if (std::abs(s - 1.0) > 0.12) {
      cv::resize(flat, flat, {}, s, s, s > 1 ? cv::INTER_CUBIC : cv::INTER_AREA);
      ink = imaging::binarize(flat);
      page.scale = s;
    }
  }
  const double th = textHeight > 0 ? textHeight * page.scale : kTargetTextHeight;
  I.dump("flat", flat);

  // 5. Rules and tables. Rules are erased before OCR: they confuse the LSTM.
  const int minH = std::max(ink.cols / 8, static_cast<int>(12 * th));
  const int minV = std::max(30, static_cast<int>(2.5 * th));
  const cv::Mat rules = imaging::rulingLines(ink, minH, minV);
  cv::Mat clean = flat.clone();
  clean.setTo(255, rules);
  I.dump("clean", clean);
  const cv::Mat textInk = ink & ~rules;

  std::vector<tables::DetectedTable> found;
  if (I.opt.detectTables) found = tables::detect(rules, th);

  cv::Mat running = clean.clone();
  for (auto& t : found) running(t.box).setTo(255);
  I.dump("running", running);

  // 6. Running text.
  std::vector<std::pair<int, Block>> ordered;
  for (auto& words : I.ocrLines(running, tesseract::PSM_AUTO)) {
    Line line;
    cv::Rect box = words.front().box;
    float confSum = 0;
    std::string joined;
    const auto refined = I.refineLine(running, words);
    for (auto& best : refined) {
      if (!joined.empty()) joined += ' ';
      joined += best.text;
      confSum += best.conf;
      box |= best.box;
    }
    if (refined.empty() || isNoise(joined)) continue;
    line.text = joined;
    line.confidence = confSum / refined.size();
    line.box = box;
    Block b;
    b.kind = Block::Kind::Text;
    b.box = box;
    b.lines.push_back(std::move(line));
    ordered.emplace_back(box.y, std::move(b));
  }

  // 7. Tables, cell by cell.
  for (auto& t : found) {
    Block b;
    b.kind = Block::Kind::Table;
    b.box = t.box;
    b.rows = t.rows;
    b.cols = t.cols;
    std::vector<cv::Mat> crops;  // parallel to b.cells; empty for blank cells
    for (auto& dc : t.cells) {
      Cell cell{dc.row, dc.col, "", 0, dc.box};
      cv::Rect inner = dc.box;
      inner.x += 3; inner.y += 3; inner.width -= 6; inner.height -= 6;
      inner &= cv::Rect(0, 0, clean.cols, clean.rows);
      if (inner.area() <= 0 || cv::countNonZero(textInk(inner)) < 0.15 * th * th) {
        b.cells.push_back(cell);
        crops.emplace_back();
        continue;
      }
      // Crop to the ink inside the cell: less blank area, fewer rule remnants,
      // and the line count follows the content, not the cell size.
      const cv::Rect content = inkBounds(textInk(inner), 0.03 * th * th) + inner.tl();
      if (content.area() <= 0) {
        b.cells.push_back(cell);
        crops.emplace_back();
        continue;
      }
      const cv::Rect snug = cv::Rect(content.x - 6, content.y - 6, content.width + 12, content.height + 12) & inner;
      const cv::Mat crop = padWhite(clean(snug), kPad);
      const bool multiLine = content.height > 1.8 * th;
      const auto psm = multiLine ? tesseract::PSM_SINGLE_BLOCK : tesseract::PSM_SINGLE_LINE;
      std::string joined;
      float confSum = 0;
      int count = 0;
      for (auto& words : I.ocrLines(crop, psm)) {
        if (!joined.empty()) joined += ' ';
        std::string lineText;
        for (auto& best : I.refineLine(crop, words)) {
          if (!lineText.empty()) lineText += ' ';
          lineText += best.text;
          confSum += best.conf;
          ++count;
        }
        joined += lineText;
      }
      if (!isNoise(joined)) {
        cell.text = trimNumberTail(joined);
        cell.confidence = count ? confSum / count : 0;
      }
      b.cells.push_back(cell);
      crops.push_back(crop);
    }
    I.rereadNumericColumns(b, crops);
    ordered.emplace_back(t.box.y, std::move(b));
  }

  std::stable_sort(ordered.begin(), ordered.end(), [](auto& a, auto& b) { return a.first < b.first; });
  for (auto& [y, b] : ordered) page.blocks.push_back(std::move(b));
  page.normalized = clean;
  return page;
}

std::string Page::text() const {
  std::ostringstream out;
  for (auto& b : blocks) {
    if (b.kind == Block::Kind::Text) {
      for (auto& l : b.lines) out << l.text << '\n';
      continue;
    }
    for (int r = 0; r < b.rows; ++r) {
      std::string row;
      for (auto& c : b.cells) {
        if (c.row != r || c.text.empty()) continue;
        if (!row.empty()) row += '\t';
        row += c.text;
      }
      if (!row.empty()) out << row << '\n';
    }
  }
  return out.str();
}

std::string Page::json() const {
  std::ostringstream o;
  auto box = [&](const cv::Rect& r) {
    o << "\"box\":[" << r.x << ',' << r.y << ',' << r.width << ',' << r.height << ']';
  };
  o << "{\"pageFound\":" << (pageFound ? "true" : "false") << ",\"script\":\"" << script << "\",\"skew\":" << skewDegrees << ",\"scale\":" << scale
    << ",\"blocks\":[";
  for (size_t i = 0; i < blocks.size(); ++i) {
    auto& b = blocks[i];
    if (i) o << ',';
    o << "{\"kind\":\"" << (b.kind == Block::Kind::Text ? "text" : "table") << "\",";
    box(b.box);
    if (b.kind == Block::Kind::Text) {
      o << ",\"lines\":[";
      for (size_t k = 0; k < b.lines.size(); ++k) {
        if (k) o << ',';
        o << "{\"text\":\"" << jsonEscape(b.lines[k].text) << "\",\"conf\":" << b.lines[k].confidence << ',';
        box(b.lines[k].box);
        o << '}';
      }
      o << ']';
    } else {
      o << ",\"rows\":" << b.rows << ",\"cols\":" << b.cols << ",\"cells\":[";
      for (size_t k = 0; k < b.cells.size(); ++k) {
        auto& c = b.cells[k];
        if (k) o << ',';
        o << "{\"row\":" << c.row << ",\"col\":" << c.col << ",\"text\":\"" << jsonEscape(c.text)
          << "\",\"conf\":" << c.confidence << ',';
        box(c.box);
        o << '}';
      }
      o << ']';
    }
    o << '}';
  }
  o << "]}";
  return o.str();
}

}  // namespace ps
