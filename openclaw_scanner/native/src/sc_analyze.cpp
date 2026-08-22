// Auto-analysis (shadow/finger/stray) + contour extraction।
// এই file-এ shadow/stray classical অংশ implemented; finger seg (ONNX) ও full
// auto_analyze compose করার জায়গা TODO দিয়ে চিহ্নিত — pattern sc_inpaint.cpp-এর মতো।
#include "scanner_core.h"
#include <opencv2/opencv.hpp>
#include <string>
#include <cstring>

extern cv::Mat asMat(const ScImage*); extern ScImage toScImage(const cv::Mat&);
extern ScStatus sc_ok(); extern ScStatus sc_fail(int, const std::string&);
struct ScScratch { std::vector<cv::Mat> pool; cv::Mat* find(const uint8_t*); };
struct ScHandSegmenter { /* ONNX seg session — sc_inpaint.cpp ধাঁচে init করুন */ };

extern "C" ScStatus sc_handseg_create(const char*, int32_t, ScHandSegmenter** out) {
  *out = new ScHandSegmenter(); return sc_ok(); // TODO: ONNX session load
}
extern "C" void sc_handseg_destroy(ScHandSegmenter* hs) { delete hs; }

extern "C" ScStatus sc_detect_shadow_mask(const ScImage* proxy, ScImage* out_mask) {
  cv::Mat img = asMat(proxy), gray, bg, mask;
  if (img.channels() > 1) cv::cvtColor(img, gray, cv::COLOR_BGR2GRAY); else gray = img;
  cv::medianBlur(gray, bg, 31);
  double gmed = cv::mean(bg)[0];
  cv::threshold(bg, mask, gmed * 0.75, 255, cv::THRESH_BINARY_INV);
  *out_mask = toScImage(mask);
  return sc_ok();
}

extern "C" ScStatus sc_detect_stray_marks(const ScImage* proxy, ScImage* out_mask) {
  cv::Mat img = asMat(proxy), gray, bin;
  if (img.channels() > 1) cv::cvtColor(img, gray, cv::COLOR_BGR2GRAY); else gray = img;
  cv::adaptiveThreshold(gray, bin, 255, cv::ADAPTIVE_THRESH_GAUSSIAN_C, cv::THRESH_BINARY_INV, 25, 10);
  *out_mask = toScImage(bin);
  return sc_ok();
}

extern "C" ScStatus sc_mask_to_contours(const ScImage* mask, double eps_frac,
                                        double min_area_frac, char** out_json) {
  cv::Mat m = asMat(mask), g;
  if (m.channels() > 1) cv::cvtColor(m, g, cv::COLOR_BGR2GRAY); else g = m;
  std::vector<std::vector<cv::Point>> contours;
  std::vector<cv::Vec4i> hier;
  cv::findContours(g, contours, hier, cv::RETR_CCOMP, cv::CHAIN_APPROX_SIMPLE);
  const double W = g.cols, H = g.rows, area = W * H;
  std::string json = "[";
  bool first = true;
  for (size_t i = 0; i < contours.size(); ++i) {
    if (cv::contourArea(contours[i]) < min_area_frac * area) continue;
    std::vector<cv::Point> ap;
    cv::approxPolyDP(contours[i], ap, eps_frac * cv::arcLength(contours[i], true), true);
    if (ap.size() < 3) continue;
    if (!first) json += ","; first = false;
    json += "[[";
    for (size_t k = 0; k < ap.size(); ++k) {
      char buf[64];
      std::snprintf(buf, sizeof buf, "%s{\"x\":%.5f,\"y\":%.5f}", k ? "," : "", ap[k].x / W, ap[k].y / H);
      json += buf;
    }
    json += "]]";
  }
  json += "]";
  *out_json = strdup(json.c_str());
  return sc_ok();
}

// TODO: shadow+finger+stray চালিয়ে, প্রতিটির contour নিয়ে
// {"shadow":[...],"finger":[...],"stray":[...]} JSON বানান।
extern "C" ScStatus sc_auto_analyze(ScHandSegmenter*, ScScratch* s, const char* src_path,
                                    int32_t max_dim, char** out_json) {
  (void)s; (void)max_dim;
  cv::Mat img = cv::imread(src_path, cv::IMREAD_COLOR);
  if (img.empty()) return sc_fail(SC_ERR_IO, "imread failed");
  // MVP: শুধু shadow → contour (finger ONNX যোগ করলে এখানে merge করুন)।
  ScImage proxy = toScImage(img), shadow{};
  ScStatus st = sc_detect_shadow_mask(&proxy, &shadow);
  sc_image_free(&proxy);
  if (st.code != 0) return st;
  char* shadowJson = nullptr;
  st = sc_mask_to_contours(&shadow, 0.01, 0.002, &shadowJson);
  sc_image_free(&shadow);
  if (st.code != 0) return st;
  std::string out = std::string("{\"shadow\":") + shadowJson + ",\"finger\":[],\"stray\":[]}";
  free(shadowJson);
  *out_json = strdup(out.c_str());
  return sc_ok();
}
