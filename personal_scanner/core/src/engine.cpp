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
// Shaded (halftone) table rows and rule fragments read as runs of dashes and
// symbols. A lone "-" is kept: tables use it for "nil".
bool isJunkToken(const std::string& s) {
  const auto u = text::decode(s);
  if (u == U"-") return false;
  for (char32_t c : u) {
    if (c > 0x7F && c != U'\u2014' && c != U'\u2013' && c != U'\u2018' && c != U'\u2019' && c != U'\u201C' &&
        c != U'\u201D')
      return false;
    if (c < 0x80 && std::isalnum(static_cast<int>(c))) return false;
  }
  return !u.empty();
}

bool hasBengali(const std::string& s) {
  for (char32_t c : text::decode(s))
    if (c >= 0x0980 && c <= 0x09FF) return true;
  return false;
}

// Bengali and Latin letters in one short cell ("৪১০৫ BOARD") mean one of the
// words was read by the wrong model.
bool mixesScripts(const std::string& s) {
  bool bengali = false, latin = false;
  for (char32_t c : text::decode(s)) {
    if (c >= 0x0980 && c <= 0x09FF) bengali = true;
    else if ((c >= U'A' && c <= U'Z') || (c >= U'a' && c <= U'z')) latin = true;
  }
  return bengali && latin;
}

// A narrow cell wraps "100302" as "10030" / "2" and "13.04.2023" as
// "13.04.202" / "3": join such lines without a space.
bool continuesNumber(const std::string& before, const std::string& next) {
  const auto a = text::decode(before), b = text::decode(next);
  if (a.empty() || b.empty() || !text::isDigit(b.front())) return false;
  const char32_t last = a.back();
  return text::isDigit(last) || last == U'.' || last == U'/';
}

// Bounding box of the ink, ignoring specks (rule-crossing remnants, dust)
// that would otherwise stretch the crop to the cell corners.
cv::Rect inkBounds(const cv::Mat& ink, double minArea, double minHeight) {
  cv::Mat labels, stats, centroids;
  const int n = cv::connectedComponentsWithStats(ink, labels, stats, centroids, 8);
  cv::Rect box;
  for (int i = 1; i < n; ++i) {
    if (stats.at<int>(i, cv::CC_STAT_AREA) < minArea) continue;
    // Halftone shading and dust are small dots; glyph parts are taller.
    if (stats.at<int>(i, cv::CC_STAT_HEIGHT) < minHeight && stats.at<int>(i, cv::CC_STAT_WIDTH) < minHeight) continue;
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

// Tesseract's layout analysis often splits one visual row into separate
// blocks: a form label in one, its value in another (worse on curled
// pages). Re-join pieces that share a row (vertical overlap, no horizontal
// overlap), left to right, so "Invoice No : HB/..." stays one line.
std::vector<Line> mergeVisualRows(std::vector<Line> pieces) {
  std::sort(pieces.begin(), pieces.end(), [](const Line& a, const Line& b) { return a.box.y < b.box.y; });
  struct Row {
    Line line;
    std::vector<cv::Rect> parts;
  };
  std::vector<Row> rows;
  for (auto& p : pieces) {
    Row* target = nullptr;
    for (auto& r : rows) {
      const int top = std::max(r.line.box.y, p.box.y);
      const int bottom = std::min(r.line.box.y + r.line.box.height, p.box.y + p.box.height);
      if (bottom - top < 0.5 * std::min(r.line.box.height, p.box.height)) continue;
      const bool collides = std::any_of(r.parts.begin(), r.parts.end(), [&](const cv::Rect& q) {
        return std::min(q.x + q.width, p.box.x + p.box.width) - std::max(q.x, p.box.x) > 0;
      });
      if (!collides) { target = &r; break; }
    }
    if (!target) {
      rows.push_back({p, {p.box}});
      continue;
    }
    // Insert left to right.
    const bool before = p.box.x < target->line.box.x;
    target->line.text = before ? p.text + ' ' + target->line.text : target->line.text + ' ' + p.text;
    const float n = static_cast<float>(target->parts.size());
    target->line.confidence = (target->line.confidence * n + p.confidence) / (n + 1);
    target->line.box |= p.box;
    target->parts.push_back(p.box);
  }
  std::vector<Line> out;
  for (auto& r : rows) out.push_back(std::move(r.line));
  std::sort(out.begin(), out.end(), [](const Line& a, const Line& b) { return a.box.y < b.box.y; });
  return out;
}

float meanConf(const std::vector<Word>& words) {
  float sum = 0;
  for (auto& w : words) sum += w.conf;
  return words.empty() ? 0 : sum / words.size();
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

  // OCR of one table cell: lines joined, numbers wrapped by the narrow cell
  // re-joined. Returns text and mean word confidence.
  std::pair<std::string, float> readCell(const cv::Mat& crop, tesseract::PageSegMode psm) {
    std::string joined;
    float confSum = 0;
    int count = 0;
    for (auto& words : ocrLines(crop, psm)) {
      std::string lineText;
      for (auto& best : refineLine(crop, words)) {
        if (!lineText.empty()) lineText += ' ';
        lineText += best.text;
        confSum += best.conf;
        ++count;
      }
      if (lineText.empty()) continue;
      if (!joined.empty() && !continuesNumber(joined, lineText)) joined += ' ';
      joined += lineText;
    }
    return {joined, count ? confSum / count : 0.0f};
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
    // "500$2.5", "5O0.00": mostly digits with a look-alike symbol inside.
    // The Latin model's classic confusions map back deterministically.
    const bool nearlyNumber = prof.digits() >= 3 && prof.other <= 1 && prof.digits() >= 3 * prof.other;
    if (nearlyNumber && !prof.numberLike()) {
      std::string fixed;
      bool ok = true;
      for (char c : first.text) {
        switch (c) {
          case '$': case 'S': fixed += '5'; break;
          case 'O': case 'o': fixed += '0'; break;
          case 'l': case 'I': case '|': fixed += '1'; break;
          default:
            if (static_cast<unsigned char>(c) >= 0x80 || std::isalpha(static_cast<unsigned char>(c))) ok = false;
            fixed += c;
        }
      }
      if (ok && text::profile(fixed).numberLike()) {
        Word w = first;
        w.text = fixed;
        return w;
      }
    }
    if (!opt.numericRereads || !prof.numberLike()) return first;
    const cv::Mat crop = cropWord(gray, first.box);
    if (crop.empty()) return first;
    // Bengali ৪ looks like Latin 8, ৭ like 9, ০ like 0: read the box in both
    // digit scripts and keep the more confident, preferring the first read's
    // script on near-ties.
    // On an English page Bengali digits are not expected; do not offer them.
    const bool latinPage = primary == &latin;
    const bool preferBengali = !latinPage && prof.bengali >= prof.latin;
    Word best = first;
    for (bool bengali : {preferBengali, !preferBengali}) {
      if (latinPage && bengali) continue;
      const Word w = readDigits(crop, bengali, tesseract::PSM_SINGLE_WORD, first);
      if (w.text.empty() || w.text.find(' ') != std::string::npos) continue;
      const float margin = bengali == preferBengali ? 0.0f : 5.0f;
      if (std::getenv("PS_TRACE")) std::fprintf(stderr, "num: '%s' %.0f -> '%s' %.0f (%s)\n", first.text.c_str(), first.conf, w.text.c_str(), w.conf, bengali ? "bn" : "latin");
      if (w.conf >= best.conf + margin) best = w;
    }
    return best;
  }

  // Forces a digits-only read of a whole cell (column known to be numeric).
  std::optional<Word> readCellAsNumber(const cv::Mat& crop, bool bengali) {
    if (!opt.numericRereads) return std::nullopt;
    // Single-word mode: single-line mode drops lone glyphs like "২". A
    // number wrapped over two lines in a narrow cell needs block mode.
    Word w = readDigits(crop, bengali, tesseract::PSM_SINGLE_WORD, Word{});
    if (w.text.empty() || w.text.find(' ') != std::string::npos) {
      Word block = readDigits(crop, bengali, tesseract::PSM_SINGLE_BLOCK, Word{});
      std::string joined;
      std::istringstream lines(block.text);
      for (std::string line; std::getline(lines, line);) {
        line = text::trim(line);
        if (line.empty()) continue;
        if (!joined.empty() && !continuesNumber(joined, line)) joined += ' ';
        joined += line;
      }
      block.text = joined;
      w = block;
    }
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
      // Typical length of a number in this column.
      std::vector<int> lengths;
      for (auto& cell : table.cells)
        if (cell.col == c && text::profile(cell.text).numberLike()) lengths.push_back(text::profile(cell.text).digits());
      std::nth_element(lengths.begin(), lengths.begin() + lengths.size() / 2, lengths.end());
      const int typical = lengths[lengths.size() / 2];
      for (size_t k = 0; k < table.cells.size(); ++k) {
        Cell& cell = table.cells[k];
        if (cell.col != c || cell.text.empty() || crops[k].empty()) continue;
        auto prof = text::profile(cell.text);
      if (prof.numberLike()) {
        // "15 1461.97": a gap inside a number is a wrap or spacing artifact.
        std::string joined;
        for (char ch : cell.text)
          if (ch != ' ') joined += ch;
        cell.text = joined;
        // Far shorter than its neighbours and not confident: likely garbled
        // ("২2" for 246509.03).
        const bool stunted = prof.digits() * 2 < typical && cell.confidence < 80;
        if (!stunted) continue;
        prof = text::profile(cell.text);
      }
      // Short misreads ("ঙ" for ৬) and weak reads that are at least half
      // digits ("8@Go00") get a digits-only read.
      const bool shortRead = text::decode(cell.text).size() <= 3;
      const bool weakNumeric = cell.confidence < 70 && 2 * prof.digits() >= prof.total();
      // "246625.8 ও": a number whose wrapped last digit was read as a letter.
      const bool nearlyNumber = prof.digits() >= 3 && prof.other <= 2 && prof.digits() >= 3 * prof.other;
      const bool stuntedNumber = prof.numberLike();  // reached only when stunted
      if (!shortRead && !weakNumeric && !nearlyNumber && !stuntedNumber) continue;
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
    // Central square: holds text in any orientation, cheap to read.
    const int side = std::min(gray.cols, gray.rows) * 2 / 3;
    const cv::Rect band((gray.cols - side) / 2, (gray.rows - side) / 2, side, side);
    setImage(api, gray(band));
    // Single-block mode: no layout analysis, so text in the wrong orientation
    // scores low instead of being found as rotated blocks.
    api.SetPageSegMode(tesseract::PSM_SINGLE_BLOCK);
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

  // 2. Lighting, then orientation and script together: read a probe region
  // in all four quarter turns with each model and keep the most confident.
  // Geometry alone fails on tilted phone photos; this does not.
  cv::Mat flat = imaging::flattenIllumination(gray);
  {
    const double s = std::min(1.0, 1600.0 / std::max(flat.cols, flat.rows));
    cv::Mat probe;
    cv::resize(flat, probe, {}, s, s, cv::INTER_AREA);
    double best = -1;
    int bestTurns = 0;
    bool latinPage = false;
    for (int turns = 0; turns < 4; ++turns) {
      const cv::Mat r = imaging::rotateQuarterTurns(probe, turns);
      const double ben = I.probeConfidence(I.main, r);
      const double eng = I.hasLatin ? I.probeConfidence(I.latin, r) : -1;
      // Bengali wins near-ties: the Bengali pipeline already rescues English words.
      const bool eng_wins = eng > ben + 10;
      const double score = std::max(ben, eng);
      if (std::getenv("PS_TRACE")) std::fprintf(stderr, "probe turns=%d ben=%.0f eng=%.0f\n", turns, ben, eng);
      if (score > best + 2) {
        best = score;
        bestTurns = turns;
        latinPage = eng_wins;
      }
    }
    flat = imaging::rotateQuarterTurns(flat, bestTurns);
    I.primary = latinPage ? &I.latin : &I.main;
    page.script = latinPage ? "latin" : "bengali";
  }

  flat = imaging::invertDarkRegions(flat);

  // 3. Deskew.
  page.skewDegrees = imaging::estimateSkew(imaging::binarize(flat), 15.0);
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
  I.dump("rules", rules);
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
  std::vector<Line> pieces;
  for (auto& words : I.ocrLines(running, tesseract::PSM_AUTO)) {
    auto refined = I.refineLine(running, words);
    if (refined.empty()) continue;
    // Page-level layout analysis sometimes garbles a line that reads fine on
    // its own (wide gaps between columns, stamps nearby). Re-read weak lines
    // in isolation and keep the more confident version.
    if (meanConf(refined) < 75) {
      cv::Rect box = refined.front().box;
      for (auto& w : refined) box |= w.box;
      const cv::Rect r = cv::Rect(box.x - 6, box.y - 6, box.width + 12, box.height + 12) & cv::Rect(0, 0, running.cols, running.rows);
      const cv::Mat crop = padWhite(running(r), kPad);
      auto again = I.ocrLines(crop, tesseract::PSM_SINGLE_BLOCK);
      std::vector<Word> merged;
      for (auto& l : again)
        for (auto& w : I.refineLine(crop, l)) {
          Word shifted = w;
          shifted.box += r.tl() - cv::Point(kPad, kPad);
          merged.push_back(shifted);
        }
      if (!merged.empty() && meanConf(merged) > meanConf(refined) + 5) refined = std::move(merged);
    }
    Line line;
    line.box = refined.front().box;
    float confSum = 0;
    for (auto& w : refined) {
      if (!line.text.empty()) line.text += ' ';
      line.text += w.text;
      confSum += w.conf;
      line.box |= w.box;
    }
    if (isNoise(line.text)) continue;
    line.confidence = confSum / refined.size();
    pieces.push_back(std::move(line));
  }
  // Recovery pass: page layout analysis sometimes drops real text as
  // "image" (next to a signature stroke, stamps, curled edges). Read any
  // line-shaped ink that no recognized word covers.
  {
    cv::Mat covered = cv::Mat::zeros(running.size(), CV_8U);
    for (auto& l : pieces) cv::rectangle(covered, l.box, 255, cv::FILLED);
    for (auto& t : found) cv::rectangle(covered, t.box, 255, cv::FILLED);
    cv::dilate(covered, covered, cv::getStructuringElement(cv::MORPH_RECT, {7, 7}));
    cv::Mat rest = imaging::binarize(running) & ~covered;
    cv::Mat blobs;
    const int kw = std::max(3, static_cast<int>(1.2 * th)), kh = std::max(1, static_cast<int>(0.25 * th));
    cv::dilate(rest, blobs, cv::getStructuringElement(cv::MORPH_RECT, {kw, kh}));
    cv::Mat labels, stats, centroids;
    const int n = cv::connectedComponentsWithStats(blobs, labels, stats, centroids, 8);
    for (int i = 1; i < n; ++i) {
      const cv::Rect r(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
                       stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
      if (r.height < 0.6 * th || r.height > 3.0 * th || r.width < 1.5 * th) continue;
      // Only wholly missed text; partly covered blobs are pieces of words
      // already read.
      if (cv::countNonZero(covered(r)) > 0.1 * r.area()) continue;
      const cv::Rect g = cv::Rect(r.x - 4, r.y - 4, r.width + 8, r.height + 8) & cv::Rect(0, 0, running.cols, running.rows);
      // Headings well above body size are often why layout analysis skipped
      // them, and the model misreads large text. Try a few scales toward body
      // size and keep the most confident read.
      std::vector<Word> bestWords;
      double bestShrink = 1.0;
      for (double target : {1.0, 1.4, 0.0}) {
        const double shrink = target > 0 ? std::min(1.0, target * th / r.height) : 1.0;
        cv::Mat region = running(g);
        if (shrink < 0.95) cv::resize(region, region, {}, shrink, shrink, cv::INTER_AREA);
        const cv::Mat crop = padWhite(region, kPad);
        auto lines = I.ocrLines(crop, tesseract::PSM_SINGLE_LINE);
        if (lines.empty()) lines = I.ocrLines(crop, tesseract::PSM_SINGLE_BLOCK);
        std::vector<Word> words;
        for (auto& l : lines)
          for (auto& w : I.refineLine(crop, l)) words.push_back(w);
        if (!words.empty() && meanConf(words) > meanConf(bestWords)) {
          bestWords = std::move(words);
          bestShrink = shrink;
        }
        if (shrink >= 0.95) break;  // further targets would not change the scale
      }
      if (!bestWords.empty() && meanConf(bestWords) >= 60) {
        Line line;
        line.box = bestWords.front().box;
        for (auto& w : bestWords) {
          if (!line.text.empty()) line.text += ' ';
          line.text += w.text;
          line.box |= w.box;
        }
        line.confidence = meanConf(bestWords);
        int alnum = 0;
        for (char32_t c : text::decode(line.text)) alnum += c > 0x7F || std::isalnum(static_cast<int>(c));
        if (alnum < 3 || isNoise(line.text)) continue;  // bullets, letter fragments
        line.box -= cv::Point(kPad, kPad);
        if (bestShrink < 0.95) {
          line.box = cv::Rect(static_cast<int>(line.box.x / bestShrink), static_cast<int>(line.box.y / bestShrink),
                              static_cast<int>(line.box.width / bestShrink), static_cast<int>(line.box.height / bestShrink));
        }
        line.box += g.tl();
        if (std::getenv("PS_TRACE")) std::fprintf(stderr, "recovered: '%s' %.0f\n", line.text.c_str(), line.confidence);
        pieces.push_back(std::move(line));
      }
    }
  }

  std::vector<std::pair<int, Block>> ordered;
  for (auto& row : mergeVisualRows(std::move(pieces))) {
    Block b;
    b.kind = Block::Kind::Text;
    b.box = row.box;
    b.lines.push_back(std::move(row));
    ordered.emplace_back(b.box.y, std::move(b));
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
      const cv::Rect content = inner.area() > 0 ? inkBounds(textInk(inner), 0.03 * th * th, 0.35 * th) + inner.tl() : cv::Rect();
      if (content.area() <= 0 || cv::countNonZero(textInk(content)) < 0.15 * th * th) {
        b.cells.push_back(cell);
        crops.emplace_back();
        continue;
      }
      // Crop to the ink inside the cell: less blank area, fewer rule remnants,
      // and the line count follows the content, not the cell size.
      const cv::Rect snug = cv::Rect(content.x - 6, content.y - 6, content.width + 12, content.height + 12) & inner;
      const cv::Mat crop = padWhite(clean(snug), kPad);
      const bool multiLine = content.height > 1.8 * th;
      const auto psm = multiLine ? tesseract::PSM_SINGLE_BLOCK : tesseract::PSM_SINGLE_LINE;
      auto [joined, conf] = I.readCell(crop, psm);
      // Single-line mode occasionally returns nothing for a short bold word
      // ("ক্রম"); block mode reads it. Try the other mode on weak reads.
      if (conf < 60) {
        const auto other = psm == tesseract::PSM_SINGLE_LINE ? tesseract::PSM_SINGLE_BLOCK : tesseract::PSM_SINGLE_LINE;
        auto [t2, c2] = I.readCell(crop, other);
        if (c2 > conf) {
          joined = t2;
          conf = c2;
        }
      }
      // Mixed-script tables (Bengali headers, English/number cells): a weak
      // read gets a second opinion from the other model.
      // A confident-enough Bengali read (letters or digits) is not handed to
      // the English model, which renders Bengali glyphs as look-alike Latin.
      const bool bengaliRead = hasBengali(joined) && !mixesScripts(joined) && conf >= 50;
      if ((conf < 75 || mixesScripts(joined)) && !bengaliRead && I.hasLatin) {
        tesseract::TessBaseAPI* saved = I.primary;
        I.primary = saved == &I.main ? &I.latin : &I.main;
        auto [otherText, otherConf] = I.readCell(crop, psm);
        I.primary = saved;
        if (std::getenv("PS_TRACE")) std::fprintf(stderr, "cell 2nd: '%s' %.0f -> '%s' %.0f\n", joined.c_str(), conf, otherText.c_str(), otherConf);
        if (otherConf > conf + 5) {
          joined = otherText;
          conf = otherConf;
        }
      }
      if (!isNoise(joined)) {
        cell.text = trimNumberTail(joined);
        cell.confidence = conf;
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
