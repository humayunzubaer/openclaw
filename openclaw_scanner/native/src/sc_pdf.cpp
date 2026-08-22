// PDFium wrapper — page_count / from_images / extract / combine / compress /
// add_text_layer। PdfService (Dart) এক long-lived isolate থেকে serialize করে ডাকে,
// তাই এখানে thread-safety ধরে নেওয়া হয়নি; sc_pdf_init() ওই isolate-এ একবার চলে।
#include "scanner_core.h"

#include "fpdfview.h"
#include "fpdf_edit.h"
#include "fpdf_ppo.h"
#include "fpdf_save.h"
#include "fpdf_text.h"

#include <opencv2/opencv.hpp>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

extern ScStatus sc_ok();
extern ScStatus sc_fail(int, const std::string&);

// ---------------------------------------------------------------- helpers ---

namespace {

// FPDF_FILEACCESS over an in-memory buffer (LoadJpegFileInline copies eagerly,
// so the buffer only needs to outlive the call).
struct MemAccess : FPDF_FILEACCESS {
  const uint8_t* buf = nullptr;
};
int memGetBlock(void* param, unsigned long pos, unsigned char* out, unsigned long size) {
  auto* ma = static_cast<MemAccess*>(param);
  if (pos + size > ma->m_FileLen) return 0;
  std::memcpy(out, ma->buf + pos, size);
  return 1;
}
MemAccess memAccess(const std::vector<uint8_t>& bytes) {
  MemAccess ma{};
  ma.m_FileLen = static_cast<unsigned long>(bytes.size());
  ma.m_GetBlock = memGetBlock;
  ma.buf = bytes.data();
  ma.m_Param = &ma;                 // fixed up by caller after copy
  return ma;
}

// FPDF_FILEWRITE straight to a FILE*.
struct FileWriter : FPDF_FILEWRITE {
  FILE* fp = nullptr;
};
int fileWriteBlock(FPDF_FILEWRITE* self, const void* data, unsigned long size) {
  FILE* fp = static_cast<FileWriter*>(self)->fp;
  return std::fwrite(data, 1, size, fp) == size ? 1 : 0;
}

ScStatus saveDocTo(FPDF_DOCUMENT doc, const char* out_path) {
  FILE* fp = std::fopen(out_path, "wb");
  if (!fp) return sc_fail(SC_ERR_IO, std::string("open out failed: ") + out_path);
  FileWriter w{};
  w.version = 1;
  w.WriteBlock = fileWriteBlock;
  w.fp = fp;
  FPDF_BOOL ok = FPDF_SaveAsCopy(doc, &w, FPDF_NO_INCREMENTAL);
  std::fclose(fp);
  return ok ? sc_ok() : sc_fail(SC_ERR_RUNTIME, "FPDF_SaveAsCopy failed");
}

bool readFile(const char* path, std::vector<uint8_t>& out) {
  FILE* fp = std::fopen(path, "rb");
  if (!fp) return false;
  std::fseek(fp, 0, SEEK_END);
  long n = std::ftell(fp);
  std::fseek(fp, 0, SEEK_SET);
  if (n < 0) { std::fclose(fp); return false; }
  out.resize(static_cast<size_t>(n));
  size_t rd = n ? std::fread(out.data(), 1, static_cast<size_t>(n), fp) : 0;
  std::fclose(fp);
  return rd == static_cast<size_t>(n);
}

// UTF-8 → UTF-16LE (null-terminated) for FPDFText_SetText (FPDF_WIDESTRING).
std::vector<unsigned short> toUtf16le(const std::string& s) {
  std::vector<unsigned short> out;
  size_t i = 0, n = s.size();
  while (i < n) {
    unsigned char c = static_cast<unsigned char>(s[i]);
    unsigned int cp = 0xFFFD;
    int len = 1;
    if (c < 0x80) { cp = c; len = 1; }
    else if ((c >> 5) == 0x6) { cp = c & 0x1F; len = 2; }
    else if ((c >> 4) == 0xE) { cp = c & 0x0F; len = 3; }
    else if ((c >> 3) == 0x1E) { cp = c & 0x07; len = 4; }
    if (i + len > n) { cp = 0xFFFD; len = 1; }
    for (int k = 1; k < len; ++k) {
      unsigned char cc = static_cast<unsigned char>(s[i + k]);
      if ((cc & 0xC0) != 0x80) { cp = 0xFFFD; len = k ? k : 1; break; }
      cp = (cp << 6) | (cc & 0x3F);
    }
    i += len;
    if (cp <= 0xFFFF) {
      out.push_back(static_cast<unsigned short>(cp));
    } else {
      cp -= 0x10000;
      out.push_back(static_cast<unsigned short>(0xD800 + (cp >> 10)));
      out.push_back(static_cast<unsigned short>(0xDC00 + (cp & 0x3FF)));
    }
  }
  out.push_back(0);
  return out;
}

// --- tiny JSON reader (placements_json is produced by our own Dart jsonEncode) ---
namespace j {
struct Val {
  int t = 0;                        // 0 null,1 bool,2 num,3 str,4 arr,5 obj
  double num = 0;
  bool bl = false;
  std::string str;
  std::shared_ptr<std::vector<Val>> arr;
  std::shared_ptr<std::vector<std::pair<std::string, Val>>> obj;
  const Val* get(const char* k) const {
    if (t != 5 || !obj) return nullptr;
    for (auto& kv : *obj) if (kv.first == k) return &kv.second;
    return nullptr;
  }
  double asNum(double d = 0) const { return t == 2 ? num : d; }
};
struct Parser {
  const char* s;
  const char* e;
  bool ok = true;
  void ws() { while (s < e && (*s == ' ' || *s == '\t' || *s == '\n' || *s == '\r')) ++s; }
  bool lit(const char* w) {
    size_t l = std::strlen(w);
    if (static_cast<size_t>(e - s) >= l && std::strncmp(s, w, l) == 0) { s += l; return true; }
    return false;
  }
  static void appendUtf8(std::string& o, unsigned int cp) {
    if (cp < 0x80) { o += static_cast<char>(cp); }
    else if (cp < 0x800) { o += static_cast<char>(0xC0 | (cp >> 6)); o += static_cast<char>(0x80 | (cp & 0x3F)); }
    else if (cp < 0x10000) { o += static_cast<char>(0xE0 | (cp >> 12)); o += static_cast<char>(0x80 | ((cp >> 6) & 0x3F)); o += static_cast<char>(0x80 | (cp & 0x3F)); }
    else { o += static_cast<char>(0xF0 | (cp >> 18)); o += static_cast<char>(0x80 | ((cp >> 12) & 0x3F)); o += static_cast<char>(0x80 | ((cp >> 6) & 0x3F)); o += static_cast<char>(0x80 | (cp & 0x3F)); }
  }
  unsigned int hex4() {
    unsigned int v = 0;
    for (int i = 0; i < 4 && s < e; ++i) {
      char c = *s++; v <<= 4;
      if (c >= '0' && c <= '9') v |= c - '0';
      else if (c >= 'a' && c <= 'f') v |= c - 'a' + 10;
      else if (c >= 'A' && c <= 'F') v |= c - 'A' + 10;
      else ok = false;
    }
    return v;
  }
  Val pstr() {
    Val v; v.t = 3; ++s;
    std::string o;
    while (s < e && *s != '"') {
      char c = *s++;
      if (c != '\\') { o += c; continue; }
      if (s >= e) { ok = false; break; }
      char d = *s++;
      switch (d) {
        case '"': o += '"'; break;   case '\\': o += '\\'; break; case '/': o += '/'; break;
        case 'n': o += '\n'; break;  case 't': o += '\t'; break;  case 'r': o += '\r'; break;
        case 'b': o += '\b'; break;  case 'f': o += '\f'; break;
        case 'u': {
          unsigned int cp = hex4();
          if (cp >= 0xD800 && cp <= 0xDBFF && e - s >= 6 && s[0] == '\\' && s[1] == 'u') {
            s += 2; unsigned int lo = hex4();
            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
          }
          appendUtf8(o, cp);
        } break;
        default: o += d;
      }
    }
    if (s < e) ++s; else ok = false;
    v.str = std::move(o);
    return v;
  }
  Val pnum() {
    char* endp = nullptr;
    double d = std::strtod(s, &endp);
    if (endp == s) { ok = false; return {}; }
    s = endp;
    Val v; v.t = 2; v.num = d;
    return v;
  }
  Val parr() {
    Val v; v.t = 4; v.arr = std::make_shared<std::vector<Val>>(); ++s; ws();
    if (s < e && *s == ']') { ++s; return v; }
    while (ok) {
      v.arr->push_back(parse()); ws();
      if (s < e && *s == ',') { ++s; continue; }
      if (s < e && *s == ']') { ++s; break; }
      ok = false;
    }
    return v;
  }
  Val pobj() {
    Val v; v.t = 5; v.obj = std::make_shared<std::vector<std::pair<std::string, Val>>>(); ++s; ws();
    if (s < e && *s == '}') { ++s; return v; }
    while (ok) {
      ws();
      if (s >= e || *s != '"') { ok = false; break; }
      Val key = pstr(); ws();
      if (s < e && *s == ':') ++s; else { ok = false; break; }
      Val val = parse();
      v.obj->push_back({key.str, std::move(val)}); ws();
      if (s < e && *s == ',') { ++s; continue; }
      if (s < e && *s == '}') { ++s; break; }
      ok = false;
    }
    return v;
  }
  Val parse() {
    ws();
    if (s >= e) { ok = false; return {}; }
    char c = *s;
    if (c == '{') return pobj();
    if (c == '[') return parr();
    if (c == '"') return pstr();
    if (c == 't') { if (lit("true")) { Val v; v.t = 1; v.bl = true; return v; } ok = false; return {}; }
    if (c == 'f') { if (lit("false")) { Val v; v.t = 1; v.bl = false; return v; } ok = false; return {}; }
    if (c == 'n') { if (lit("null")) return {}; ok = false; return {}; }
    return pnum();
  }
};
}  // namespace j

int cvTypeForFormat(int fmt) {
  switch (fmt) {
    case FPDFBitmap_Gray: return CV_8UC1;
    case FPDFBitmap_BGR:  return CV_8UC3;
    default:              return CV_8UC4;  // BGRx / BGRA
  }
}

}  // namespace

// ---------------------------------------------------------------- API ---

extern "C" void sc_pdf_init(void) {
  FPDF_LIBRARY_CONFIG cfg{};
  cfg.version = 2;
  FPDF_InitLibraryWithConfig(&cfg);
}

extern "C" int32_t sc_pdf_page_count(const char* path) {
  FPDF_DOCUMENT doc = FPDF_LoadDocument(path, nullptr);
  if (!doc) return -1;
  int n = FPDF_GetPageCount(doc);
  FPDF_CloseDocument(doc);
  return n;
}

extern "C" ScStatus sc_pdf_from_images(const char* const* jpg_paths, int32_t count,
                                       double page_w_pt, double page_h_pt, const char* out_path) {
  if (count <= 0 || page_w_pt <= 0 || page_h_pt <= 0) return sc_fail(SC_ERR_INVALID, "from_images: bad args");
  FPDF_DOCUMENT doc = FPDF_CreateNewDocument();
  if (!doc) return sc_fail(SC_ERR_RUNTIME, "CreateNewDocument failed");

  for (int32_t i = 0; i < count; ++i) {
    std::vector<uint8_t> bytes;
    if (!readFile(jpg_paths[i], bytes)) { FPDF_CloseDocument(doc); return sc_fail(SC_ERR_IO, std::string("read jpg failed: ") + jpg_paths[i]); }

    FPDF_PAGE page = FPDFPage_New(doc, i, page_w_pt, page_h_pt);
    FPDF_PAGEOBJECT img = FPDFPageObj_NewImageObj(doc);

    MemAccess ma = memAccess(bytes);
    ma.m_Param = &ma;
    if (!FPDFImageObj_LoadJpegFileInline(&page, 1, img, &ma)) {
      FPDFPage_Delete(doc, i); FPDF_CloseDocument(doc);
      return sc_fail(SC_ERR_RUNTIME, std::string("LoadJpegFileInline failed: ") + jpg_paths[i]);
    }

    // Fit within the page preserving aspect ratio, centered (avoids distortion
    // when a scan's aspect differs from the requested page size).
    unsigned int iw = 0, ih = 0;
    double drawW = page_w_pt, drawH = page_h_pt, offX = 0, offY = 0;
    if (FPDFImageObj_GetImagePixelSize(img, &iw, &ih) && iw > 0 && ih > 0) {
      double imgAspect = static_cast<double>(iw) / static_cast<double>(ih);
      double pageAspect = page_w_pt / page_h_pt;
      if (pageAspect > imgAspect) { drawH = page_h_pt; drawW = page_h_pt * imgAspect; }
      else                        { drawW = page_w_pt; drawH = page_w_pt / imgAspect; }
      offX = (page_w_pt - drawW) / 2.0;
      offY = (page_h_pt - drawH) / 2.0;
    }
    FS_MATRIX m{static_cast<float>(drawW), 0, 0, static_cast<float>(drawH),
                static_cast<float>(offX), static_cast<float>(offY)};
    FPDFPageObj_SetMatrix(img, &m);

    FPDFPage_InsertObject(page, img);
    FPDFPage_GenerateContent(page);
    FPDF_ClosePage(page);
  }

  ScStatus st = saveDocTo(doc, out_path);
  FPDF_CloseDocument(doc);
  return st;
}

extern "C" ScStatus sc_pdf_extract(const char* src_path, const int32_t* indices, int32_t count,
                                   const char* out_path) {
  if (count <= 0) return sc_fail(SC_ERR_INVALID, "extract: empty selection");
  FPDF_DOCUMENT src = FPDF_LoadDocument(src_path, nullptr);
  if (!src) return sc_fail(SC_ERR_IO, std::string("load failed: ") + src_path);
  FPDF_DOCUMENT dst = FPDF_CreateNewDocument();
  if (!dst) { FPDF_CloseDocument(src); return sc_fail(SC_ERR_RUNTIME, "CreateNewDocument failed"); }

  std::vector<int> idx(indices, indices + count);
  FPDF_BOOL ok = FPDF_ImportPagesByIndex(dst, src, idx.data(), static_cast<unsigned long>(idx.size()), 0);
  ScStatus st = ok ? saveDocTo(dst, out_path) : sc_fail(SC_ERR_RUNTIME, "ImportPagesByIndex failed");
  FPDF_CloseDocument(dst);
  FPDF_CloseDocument(src);
  return st;
}

extern "C" ScStatus sc_pdf_combine(const char* const* src_paths, int32_t count, const char* out_path) {
  if (count <= 0) return sc_fail(SC_ERR_INVALID, "combine: nothing to combine");
  FPDF_DOCUMENT dst = FPDF_CreateNewDocument();
  if (!dst) return sc_fail(SC_ERR_RUNTIME, "CreateNewDocument failed");

  for (int32_t i = 0; i < count; ++i) {
    FPDF_DOCUMENT src = FPDF_LoadDocument(src_paths[i], nullptr);
    if (!src) { FPDF_CloseDocument(dst); return sc_fail(SC_ERR_IO, std::string("load failed: ") + src_paths[i]); }
    // Append at the end (NULL pagerange = all pages).
    FPDF_BOOL ok = FPDF_ImportPages(dst, src, nullptr, FPDF_GetPageCount(dst));
    FPDF_CloseDocument(src);
    if (!ok) { FPDF_CloseDocument(dst); return sc_fail(SC_ERR_RUNTIME, std::string("ImportPages failed: ") + src_paths[i]); }
  }

  ScStatus st = saveDocTo(dst, out_path);
  FPDF_CloseDocument(dst);
  return st;
}

extern "C" ScStatus sc_pdf_compress(const char* src_path, int32_t target_dpi, int32_t quality,
                                    const char* out_path) {
  if (target_dpi <= 0) target_dpi = 200;
  if (quality <= 0 || quality > 100) quality = 75;
  FPDF_DOCUMENT doc = FPDF_LoadDocument(src_path, nullptr);
  if (!doc) return sc_fail(SC_ERR_IO, std::string("load failed: ") + src_path);

  const int pages = FPDF_GetPageCount(doc);
  for (int pi = 0; pi < pages; ++pi) {
    FPDF_PAGE page = FPDF_LoadPage(doc, pi);
    if (!page) continue;
    bool changed = false;
    const int objs = FPDFPage_CountObjects(page);
    for (int oi = 0; oi < objs; ++oi) {
      FPDF_PAGEOBJECT o = FPDFPage_GetObject(page, oi);
      if (!o || FPDFPageObj_GetType(o) != FPDF_PAGEOBJ_IMAGE) continue;

      FS_MATRIX mtx{};
      if (!FPDFPageObj_GetMatrix(o, &mtx)) continue;
      const double dispW = std::fabs(mtx.a);   // displayed width in points (shear ignored)

      FPDF_BITMAP bmp = FPDFImageObj_GetBitmap(o);
      if (!bmp) continue;
      const int bw = FPDFBitmap_GetWidth(bmp);
      const int bh = FPDFBitmap_GetHeight(bmp);
      const int stride = FPDFBitmap_GetStride(bmp);
      const int fmt = FPDFBitmap_GetFormat(bmp);
      void* buf = FPDFBitmap_GetBuffer(bmp);
      if (bw <= 0 || bh <= 0 || !buf || fmt == FPDFBitmap_Unknown) { FPDFBitmap_Destroy(bmp); continue; }

      cv::Mat src(bh, bw, cvTypeForFormat(fmt), buf, static_cast<size_t>(stride));
      cv::Mat bgr;
      if (fmt == FPDFBitmap_Gray || fmt == FPDFBitmap_BGR) bgr = src;
      else cv::cvtColor(src, bgr, cv::COLOR_BGRA2BGR);

      // Only ever downscale: cap the raster at target_dpi for its displayed size.
      const double targetW = std::max(1.0, dispW / 72.0 * target_dpi);
      const double scale = (bw > targetW) ? (targetW / bw) : 1.0;
      const int nw = std::max(1, static_cast<int>(std::lround(bw * scale)));
      const int nh = std::max(1, static_cast<int>(std::lround(bh * scale)));

      cv::Mat resized;
      if (nw != bw || nh != bh) cv::resize(bgr, resized, cv::Size(nw, nh), 0, 0, cv::INTER_AREA);
      else resized = bgr;

      std::vector<uint8_t> jpg;
      cv::imencode(".jpg", resized, jpg, {cv::IMWRITE_JPEG_QUALITY, quality});
      FPDFBitmap_Destroy(bmp);
      if (jpg.empty()) continue;

      // Reload smaller JPEG into the same object; its matrix (placement) is kept.
      MemAccess ma = memAccess(jpg);
      ma.m_Param = &ma;
      if (FPDFImageObj_LoadJpegFileInline(&page, 1, o, &ma)) changed = true;
    }
    if (changed) FPDFPage_GenerateContent(page);
    FPDF_ClosePage(page);
  }

  ScStatus st = saveDocTo(doc, out_path);
  FPDF_CloseDocument(doc);
  return st;
}

extern "C" ScStatus sc_pdf_add_text_layer(const char* pdf_in, const char* pdf_out,
                                          const char* font_ttf_path, const char* placements_json) {
  std::vector<uint8_t> font;
  if (!readFile(font_ttf_path, font) || font.empty())
    return sc_fail(SC_ERR_IO, std::string("read font failed: ") + font_ttf_path);

  std::string js = placements_json ? placements_json : "[]";
  j::Parser parser{js.data(), js.data() + js.size()};
  j::Val root = parser.parse();
  if (!parser.ok || root.t != 4) return sc_fail(SC_ERR_INVALID, "placements_json parse failed");

  FPDF_DOCUMENT doc = FPDF_LoadDocument(pdf_in, nullptr);
  if (!doc) return sc_fail(SC_ERR_IO, std::string("load failed: ") + pdf_in);

  // CID TrueType font → Type0 with a ToUnicode map, so Bengali stays searchable.
  FPDF_FONT f = FPDFText_LoadFont(doc, font.data(), static_cast<uint32_t>(font.size()),
                                  FPDF_FONT_TRUETYPE, /*cid=*/1);
  if (!f) { FPDF_CloseDocument(doc); return sc_fail(SC_ERR_MODEL, "FPDFText_LoadFont failed"); }

  const int pageCount = FPDF_GetPageCount(doc);
  for (auto& entry : *root.arr) {
    if (entry.t != 5) continue;
    const j::Val* pageV = entry.get("page");
    const j::Val* items = entry.get("items");
    int pageIdx = pageV ? static_cast<int>(pageV->asNum(0)) : -1;
    if (pageIdx < 0 || pageIdx >= pageCount || !items || items->t != 4) continue;

    FPDF_PAGE page = FPDF_LoadPage(doc, pageIdx);
    if (!page) continue;
    const double pw = FPDF_GetPageWidth(page);
    const double ph = FPDF_GetPageHeight(page);

    for (auto& it : *items->arr) {
      if (it.t != 5) continue;
      const j::Val* tv = it.get("text");
      if (!tv || tv->t != 3 || tv->str.empty()) continue;
      const double xN = it.get("x") ? it.get("x")->asNum(0) : 0;
      const double yN = it.get("y") ? it.get("y")->asNum(0) : 0;   // top-left origin
      const double hN = it.get("h") ? it.get("h")->asNum(0) : 0;

      const double hPts = std::max(1.0, hN * ph);
      const float fontSize = static_cast<float>(hPts);
      const double xPts = xN * pw;
      // Screen y (top-down) → PDF y (bottom-up); baseline near the box bottom.
      const double baselineY = ph - (yN * ph) - hPts * 0.8;

      FPDF_PAGEOBJECT t = FPDFPageObj_CreateTextObj(doc, f, fontSize);
      if (!t) continue;
      std::vector<unsigned short> u16 = toUtf16le(tv->str);
      FPDFText_SetText(t, reinterpret_cast<FPDF_WIDESTRING>(u16.data()));
      FPDFTextObj_SetTextRenderMode(t, FPDF_TEXTRENDERMODE_INVISIBLE);
      FPDFPageObj_Transform(t, 1, 0, 0, 1, xPts, baselineY);
      FPDFPage_InsertObject(page, t);
    }

    FPDFPage_GenerateContent(page);
    FPDF_ClosePage(page);
  }

  FPDFFont_Close(f);
  ScStatus st = saveDocTo(doc, pdf_out);
  FPDF_CloseDocument(doc);
  return st;
}
