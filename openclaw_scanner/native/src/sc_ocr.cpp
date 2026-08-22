#include "scanner_core.h"
#include <opencv2/opencv.hpp>
#include <tesseract/baseapi.h>
#include <string>
#include <cstring>

extern cv::Mat asMat(const ScImage*); extern ScStatus sc_ok(); extern ScStatus sc_fail(int, const std::string&);

struct ScOcrEngine { tesseract::TessBaseAPI api; };

static std::string jsonEscape(const char* s) {          // Bengali UTF-8 pass-through
  std::string o;
  for (const char* p = s; *p; ++p) {
    switch (*p) {
      case '"': o += "\\\""; break; case '\\': o += "\\\\"; break;
      case '\n': o += "\\n"; break; case '\r': break; case '\t': o += "\\t"; break;
      default: o += *p;
    }
  }
  return o;
}

extern "C" ScStatus sc_ocr_create(const char* dir, const char* lang, ScOcrEngine** out) {
  auto* e = new ScOcrEngine();
  if (e->api.Init(dir, lang, tesseract::OEM_LSTM_ONLY) != 0) {   // ben.traineddata, LSTM
    delete e; return sc_fail(SC_ERR_MODEL, "tesseract Init failed (tessdata dir + ben.traineddata check)");
  }
  e->api.SetPageSegMode(tesseract::PSM_AUTO);
  *out = e; return sc_ok();
}
extern "C" void sc_ocr_destroy(ScOcrEngine* e) { if (e) { e->api.End(); delete e; } }

extern "C" ScStatus sc_ocr_recognize(ScOcrEngine* e, const ScImage* page, char** out_json) {
  cv::Mat m = asMat(page), gray;
  if (m.channels() == 1) gray = m; else cv::cvtColor(m, gray, cv::COLOR_BGR2GRAY);
  e->api.SetImage(gray.data, gray.cols, gray.rows, 1, (int)gray.step);
  e->api.Recognize(nullptr);

  const int W = gray.cols, H = gray.rows;
  std::string json = "[";
  bool first = true; int lineNo = 0;
  tesseract::ResultIterator* it = e->api.GetIterator();
  const auto L = tesseract::RIL_WORD;
  if (it) {
    do {
      if (it->Empty(L)) continue;
      if (it->IsAtBeginningOf(tesseract::RIL_TEXTLINE)) ++lineNo;
      char* w = it->GetUTF8Text(L);
      if (!w) continue;
      float conf = it->Confidence(L);
      int x1, y1, x2, y2; it->BoundingBox(L, &x1, &y1, &x2, &y2);
      if (!first) json += ","; first = false;
      char geo[512];
      std::snprintf(geo, sizeof geo,
        "{\"text\":\"%s\",\"x\":%.5f,\"y\":%.5f,\"w\":%.5f,\"h\":%.5f,\"conf\":%.1f,\"line\":\"L%d\"}",
        jsonEscape(w).c_str(), (double)x1 / W, (double)y1 / H,
        (double)(x2 - x1) / W, (double)(y2 - y1) / H, conf, lineNo);
      json += geo;
      delete[] w;
    } while (it->Next(L));
    delete it;
  }
  json += "]";
  *out_json = strdup(json.c_str());     // Dart sc_string_free দিয়ে free করে
  return sc_ok();
}
