#include "scanner_core.h"
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

extern cv::Mat asMat(const ScImage*); extern ScImage toScImage(const cv::Mat&);
extern ScImage viewOf(cv::Mat&); extern ScStatus sc_ok(); extern ScStatus sc_fail(int, const std::string&);
struct ScScratch { std::vector<cv::Mat> pool; cv::Mat* find(const uint8_t*); };

static void orderCorners(const std::vector<cv::Point>& p, ScQuad* q) {
  int tl = 0, br = 0, tr = 0, bl = 0;
  for (int i = 1; i < 4; ++i) {
    if (p[i].x + p[i].y < p[tl].x + p[tl].y) tl = i;
    if (p[i].x + p[i].y > p[br].x + p[br].y) br = i;
    if (p[i].x - p[i].y > p[tr].x - p[tr].y) tr = i;
    if (p[i].x - p[i].y < p[bl].x - p[bl].y) bl = i;
  }
  q->tl = {(float)p[tl].x, (float)p[tl].y}; q->tr = {(float)p[tr].x, (float)p[tr].y};
  q->br = {(float)p[br].x, (float)p[br].y}; q->bl = {(float)p[bl].x, (float)p[bl].y};
}

extern "C" ScStatus sc_detect_document_quad(const ScImage* src, ScQuad* out) {
  cv::Mat img = asMat(src), gray, edges;
  if (img.channels() > 1) cv::cvtColor(img, gray, cv::COLOR_BGR2GRAY); else gray = img;
  cv::GaussianBlur(gray, gray, {5, 5}, 0);
  cv::Canny(gray, edges, 60, 180);
  cv::dilate(edges, edges, cv::Mat(), {-1, -1}, 1);
  std::vector<std::vector<cv::Point>> contours;
  cv::findContours(edges, contours, cv::RETR_LIST, cv::CHAIN_APPROX_SIMPLE);
  double best = 0; std::vector<cv::Point> quad;
  for (auto& c : contours) {
    double area = cv::contourArea(c);
    if (area < 0.2 * img.total()) continue;
    std::vector<cv::Point> ap;
    cv::approxPolyDP(c, ap, 0.02 * cv::arcLength(c, true), true);
    if (ap.size() == 4 && cv::isContourConvex(ap) && area > best) { best = area; quad = ap; }
  }
  if (quad.size() != 4) {
    out->tl = {0, 0}; out->tr = {(float)img.cols, 0};
    out->br = {(float)img.cols, (float)img.rows}; out->bl = {0, (float)img.rows};
    return sc_ok();
  }
  orderCorners(quad, out);
  return sc_ok();
}

extern "C" ScStatus sc_warp_perspective(const ScImage* src, const ScQuad* q, ScImage* out) {
  cv::Mat img = asMat(src);
  cv::Point2f s[4] = {{q->tl.x, q->tl.y}, {q->tr.x, q->tr.y}, {q->br.x, q->br.y}, {q->bl.x, q->bl.y}};
  float wTop = cv::norm(s[1] - s[0]), wBot = cv::norm(s[2] - s[3]);
  float hL = cv::norm(s[3] - s[0]), hR = cv::norm(s[2] - s[1]);
  int W = (int)std::max(wTop, wBot), H = (int)std::max(hL, hR);
  if (W < 1 || H < 1) return sc_fail(SC_ERR_INVALID, "bad quad");
  cv::Point2f d[4] = {{0, 0}, {(float)W - 1, 0}, {(float)W - 1, (float)H - 1}, {0, (float)H - 1}};
  cv::Mat M = cv::getPerspectiveTransform(s, d), warped;
  cv::warpPerspective(img, warped, M, {W, H});
  *out = toScImage(warped);
  return sc_ok();
}

extern "C" ScStatus sc_remove_shadow(const ScImage* src, ScImage* out) {
  cv::Mat img = asMat(src);
  std::vector<cv::Mat> ch, res;
  cv::split(img, ch);
  for (auto& plane : ch) {
    cv::Mat dil, bg, diff;
    cv::dilate(plane, dil, cv::getStructuringElement(cv::MORPH_RECT, {7, 7}));
    cv::medianBlur(dil, bg, 21);
    cv::absdiff(plane, bg, diff);
    cv::Mat norm = 255 - diff;
    cv::normalize(norm, norm, 0, 255, cv::NORM_MINMAX);
    res.push_back(norm);
  }
  cv::Mat merged; cv::merge(res, merged);
  *out = toScImage(merged);
  return sc_ok();
}

static cv::Mat preprocessForOcr(const cv::Mat& in) {
  cv::Mat gray;
  if (in.channels() > 1) cv::cvtColor(in, gray, cv::COLOR_BGR2GRAY); else gray = in.clone();
  cv::Mat bin;
  cv::threshold(gray, bin, 0, 255, cv::THRESH_BINARY_INV | cv::THRESH_OTSU);
  std::vector<cv::Point> pts; cv::findNonZero(bin, pts);
  if (!pts.empty()) {
    cv::RotatedRect rr = cv::minAreaRect(pts);
    double angle = rr.angle; if (angle < -45) angle += 90;
    if (std::abs(angle) > 0.5) {
      cv::Mat R = cv::getRotationMatrix2D({gray.cols / 2.f, gray.rows / 2.f}, angle, 1.0);
      cv::warpAffine(gray, gray, R, gray.size(), cv::INTER_CUBIC, cv::BORDER_REPLICATE);
    }
  }
  cv::fastNlMeansDenoising(gray, gray, 7);
  cv::adaptiveThreshold(gray, gray, 255, cv::ADAPTIVE_THRESH_GAUSSIAN_C, cv::THRESH_BINARY, 31, 15);
  return gray;
}

extern "C" ScStatus sc_preprocess_for_ocr(const ScImage* src, ScImage* out) {
  *out = toScImage(preprocessForOcr(asMat(src)));
  return sc_ok();
}
extern "C" ScStatus sc_scratch_preprocess_for_ocr(ScScratch* s, ScImage* io) {
  cv::Mat* m = s->find(io->data);
  if (!m) return sc_fail(SC_ERR_INVALID, "view not in scratch");
  *m = preprocessForOcr(*m);
  *io = viewOf(*m);
  return sc_ok();
}

extern "C" ScStatus sc_resize(const ScImage* src, int32_t w, int32_t h, int32_t interp, ScImage* out) {
  cv::Mat dst; cv::resize(asMat(src), dst, {w, h}, 0, 0, interp ? cv::INTER_AREA : cv::INTER_LINEAR);
  *out = toScImage(dst);
  return sc_ok();
}

extern "C" ScStatus sc_image_save_file(const ScImage* img, const char* path, int32_t q) {
  std::vector<int> p{cv::IMWRITE_JPEG_QUALITY, q};
  return cv::imwrite(path, asMat(img), p) ? sc_ok() : sc_fail(SC_ERR_IO, "imwrite failed");
}

// NOTE: true page-curl dewarp = model-based (DewarpNet); আপাতত illumination flatten।
extern "C" ScStatus sc_dewarp_book(const ScImage* src, ScImage* out) { return sc_remove_shadow(src, out); }
