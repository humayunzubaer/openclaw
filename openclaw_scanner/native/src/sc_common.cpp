#include "scanner_core.h"
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>

namespace { thread_local std::string g_err; }

ScStatus sc_ok()                              { return ScStatus{SC_OK, ""}; }
ScStatus sc_fail(int c, const std::string& m) { g_err = m; return ScStatus{c, g_err.c_str()}; }

static int cvType(int fmt) {
  switch (fmt) { case SC_GRAY8: return CV_8UC1; case SC_RGB888: return CV_8UC3; default: return CV_8UC4; }
}
static int scFmt(const cv::Mat& m) {
  switch (m.channels()) { case 1: return SC_GRAY8; case 3: return SC_RGB888; default: return SC_RGBA8888; }
}
cv::Mat asMat(const ScImage* img) {
  return cv::Mat(img->height, img->width, cvType(img->format), img->data, img->stride);
}
ScImage toScImage(const cv::Mat& m) {          // malloc + copy; sc_image_free দিয়ে free
  ScImage o{}; o.width = m.cols; o.height = m.rows; o.format = scFmt(m); o.stride = (int)m.step;
  size_t bytes = m.step * m.rows;
  o.data = (uint8_t*)malloc(bytes);
  std::memcpy(o.data, m.data, bytes);
  return o;
}
ScImage viewOf(cv::Mat& m) {                    // arena memory borrow করে; free করবেন না
  ScImage v{}; v.data = m.data; v.width = m.cols; v.height = m.rows; v.stride = (int)m.step; v.format = scFmt(m);
  return v;
}

extern "C" void sc_image_free(ScImage* img) { if (img && img->data) { free(img->data); img->data = nullptr; } }
extern "C" void sc_string_free(char* s)     { if (s) free(s); }

// --- scratch arena: reusable cv::Mat slot ---
struct ScScratch {
  std::vector<cv::Mat> pool;
  cv::Mat* find(const uint8_t* d) { for (auto& m : pool) if (m.data == d) return &m; return nullptr; }
};

extern "C" ScStatus sc_scratch_create(int32_t, ScScratch** out) { *out = new ScScratch(); return sc_ok(); }
extern "C" void     sc_scratch_reset(ScScratch* s)   { if (s) s->pool.clear(); }
extern "C" void     sc_scratch_destroy(ScScratch* s) { delete s; }

extern "C" ScStatus sc_scratch_load_file(ScScratch* s, const char* path, ScImage* out_view) {
  cv::Mat m = cv::imread(path, cv::IMREAD_COLOR);       // BGR
  if (m.empty()) return sc_fail(SC_ERR_IO, std::string("imread failed: ") + path);
  s->pool.push_back(m);
  *out_view = viewOf(s->pool.back());
  return sc_ok();
}
extern "C" ScStatus sc_scratch_save_file(ScScratch*, const ScImage* view, const char* path, int32_t quality) {
  std::vector<int> p{cv::IMWRITE_JPEG_QUALITY, quality};
  return cv::imwrite(path, asMat(view), p) ? sc_ok() : sc_fail(SC_ERR_IO, "imwrite failed");
}
