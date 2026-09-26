#include "imaging.hpp"

#include <algorithm>
#include <cmath>

#include <opencv2/imgproc.hpp>

namespace ps::imaging {

cv::Mat toGray(const cv::Mat& image) {
  if (image.channels() == 1) return image.clone();
  cv::Mat gray;
  cv::cvtColor(image, gray, image.channels() == 4 ? cv::COLOR_BGRA2GRAY : cv::COLOR_BGR2GRAY);
  return gray;
}

namespace {

std::vector<cv::Point2f> orderCorners(const std::vector<cv::Point2f>& p) {
  // tl has the smallest x+y, br the largest; tr the largest x-y, bl the smallest.
  std::vector<cv::Point2f> out(4);
  auto sum = [](const cv::Point2f& q) { return q.x + q.y; };
  auto diff = [](const cv::Point2f& q) { return q.x - q.y; };
  out[0] = *std::min_element(p.begin(), p.end(), [&](auto& a, auto& b) { return sum(a) < sum(b); });
  out[2] = *std::max_element(p.begin(), p.end(), [&](auto& a, auto& b) { return sum(a) < sum(b); });
  out[1] = *std::max_element(p.begin(), p.end(), [&](auto& a, auto& b) { return diff(a) < diff(b); });
  out[3] = *std::min_element(p.begin(), p.end(), [&](auto& a, auto& b) { return diff(a) < diff(b); });
  return out;
}

}  // namespace

std::optional<std::vector<cv::Point2f>> findPage(const cv::Mat& gray) {
  // Work small: page outlines are large structures.
  const double s = 800.0 / std::max(gray.cols, gray.rows);
  cv::Mat small, blur, mask;
  cv::resize(gray, small, {}, s, s, cv::INTER_AREA);
  cv::GaussianBlur(small, blur, {7, 7}, 0);
  // Paper is brighter than the surface it lies on.
  cv::threshold(blur, mask, 0, 255, cv::THRESH_BINARY | cv::THRESH_OTSU);
  cv::morphologyEx(mask, mask, cv::MORPH_CLOSE, cv::getStructuringElement(cv::MORPH_RECT, {15, 15}));

  std::vector<std::vector<cv::Point>> contours;
  cv::findContours(mask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
  if (contours.empty()) return std::nullopt;
  auto biggest = std::max_element(contours.begin(), contours.end(),
                                  [](auto& a, auto& b) { return cv::contourArea(a) < cv::contourArea(b); });
  const double area = cv::contourArea(*biggest);
  const double imageArea = static_cast<double>(small.total());
  // Under 25%: not a page. Over 97%: the sheet already fills the frame (a scan).
  if (area < 0.25 * imageArea || area > 0.97 * imageArea) return std::nullopt;

  std::vector<cv::Point> hull, approx;
  cv::convexHull(*biggest, hull);
  for (double eps = 0.01; eps <= 0.08 && approx.size() != 4; eps += 0.005) {
    cv::approxPolyDP(hull, approx, eps * cv::arcLength(hull, true), true);
  }
  std::vector<cv::Point2f> corners;
  if (approx.size() == 4) {
    for (auto& p : approx) corners.emplace_back(p.x / s, p.y / s);
  } else {
    cv::Point2f box[4];
    cv::minAreaRect(hull).points(box);
    for (auto& p : box) corners.emplace_back(p.x / s, p.y / s);
  }
  return orderCorners(corners);
}

cv::Mat warpPage(const cv::Mat& image, const std::vector<cv::Point2f>& q) {
  const float w = std::max(cv::norm(q[1] - q[0]), cv::norm(q[2] - q[3]));
  const float h = std::max(cv::norm(q[3] - q[0]), cv::norm(q[2] - q[1]));
  const std::vector<cv::Point2f> dst = {{0, 0}, {w - 1, 0}, {w - 1, h - 1}, {0, h - 1}};
  cv::Mat out;
  cv::warpPerspective(image, out, cv::getPerspectiveTransform(q, dst), cv::Size(std::lround(w), std::lround(h)),
                      cv::INTER_CUBIC, cv::BORDER_REPLICATE);
  return out;
}

cv::Mat flattenIllumination(const cv::Mat& gray) {
  // Background = large-scale maximum filter (closing removes dark ink), then
  // smoothed. Estimated on a reduced image: lighting varies slowly.
  const double s = 0.25;
  cv::Mat small, bg;
  cv::resize(gray, small, {}, s, s, cv::INTER_AREA);
  const int k = std::max(9, (std::min(small.cols, small.rows) / 40) | 1);
  cv::morphologyEx(small, bg, cv::MORPH_CLOSE, cv::getStructuringElement(cv::MORPH_ELLIPSE, {k, k}));
  cv::GaussianBlur(bg, bg, {0, 0}, k);
  cv::resize(bg, bg, gray.size(), 0, 0, cv::INTER_LINEAR);

  cv::Mat g32, b32, flat;
  gray.convertTo(g32, CV_32F);
  bg.convertTo(b32, CV_32F);
  cv::divide(g32, cv::max(b32, 1.0), flat, 255.0);
  cv::Mat out;
  flat.convertTo(out, CV_8U);
  // Stretch so the darkest ink goes to black (photos are low contrast).
  double lo = 0, hi = 255;
  cv::Mat hist;
  int channels[] = {0}, bins[] = {256};
  float range[] = {0, 256};
  const float* ranges[] = {range};
  cv::calcHist(&out, 1, channels, cv::Mat(), hist, 1, bins, ranges);
  double total = out.total(), acc = 0;
  for (int i = 0; i < 256; ++i) {
    acc += hist.at<float>(i);
    if (acc >= total * 0.005) { lo = i; break; }
  }
  if (lo > 0 && lo < 200) {
    out.convertTo(out, CV_8U, 255.0 / (hi - lo), -lo * 255.0 / (hi - lo));
  }
  return out;
}

cv::Mat binarize(const cv::Mat& flat) {
  cv::Mat ink;
  cv::threshold(flat, ink, 0, 255, cv::THRESH_BINARY_INV | cv::THRESH_OTSU);
  return ink;
}

double estimateSkew(const cv::Mat& ink, double maxDegrees) {
  const double s = 1000.0 / std::max(ink.cols, ink.rows);
  cv::Mat small;
  cv::resize(ink, small, {}, s, s, cv::INTER_AREA);
  auto sharpness = [&](double deg) {
    cv::Mat r = rotate(small, deg, 0), rows;
    cv::reduce(r, rows, 1, cv::REDUCE_SUM, CV_64F);
    double score = 0;
    for (int i = 1; i < rows.rows; ++i) {
      const double d = rows.at<double>(i) - rows.at<double>(i - 1);
      score += d * d;
    }
    return score;
  };
  double best = 0, bestScore = -1;
  for (double d = -maxDegrees; d <= maxDegrees + 1e-9; d += 0.5) {
    const double sc = sharpness(d);
    if (sc > bestScore) { bestScore = sc; best = d; }
  }
  for (double d = best - 0.5; d <= best + 0.5 + 1e-9; d += 0.1) {
    const double sc = sharpness(d);
    if (sc > bestScore) { bestScore = sc; best = d; }
  }
  return best;
}

cv::Mat rotate(const cv::Mat& image, double degrees, int borderValue) {
  if (std::abs(degrees) < 1e-6) return image.clone();
  const cv::Point2f c(image.cols / 2.0f, image.rows / 2.0f);
  cv::Mat out;
  cv::warpAffine(image, out, cv::getRotationMatrix2D(c, degrees, 1.0), image.size(), cv::INTER_CUBIC,
                 cv::BORDER_CONSTANT, cv::Scalar::all(borderValue));
  return out;
}

cv::Mat rotateQuarterTurns(const cv::Mat& image, int turns) {
  cv::Mat out;
  switch (((turns % 4) + 4) % 4) {
    case 1: cv::rotate(image, out, cv::ROTATE_90_CLOCKWISE); return out;
    case 2: cv::rotate(image, out, cv::ROTATE_180); return out;
    case 3: cv::rotate(image, out, cv::ROTATE_90_COUNTERCLOCKWISE); return out;
    default: return image.clone();
  }
}

double medianTextHeight(const cv::Mat& ink) {
  cv::Mat labels, stats, centroids;
  const int n = cv::connectedComponentsWithStats(ink, labels, stats, centroids, 8);
  std::vector<int> heights;
  for (int i = 1; i < n; ++i) {
    const int w = stats.at<int>(i, cv::CC_STAT_WIDTH), h = stats.at<int>(i, cv::CC_STAT_HEIGHT);
    // Bengali words are joined by the matra, so components are word-sized.
    // Skip specks, ruling lines and big boxes.
    if (h < 8 || h > ink.rows / 10 || w > ink.cols / 3 || w < 4) continue;
    if (w > 25 * h || h > 8 * w) continue;
    heights.push_back(h);
  }
  if (heights.size() < 10) return 0;
  std::nth_element(heights.begin(), heights.begin() + heights.size() / 2, heights.end());
  return heights[heights.size() / 2];
}

cv::Mat rulingLines(const cv::Mat& ink, int minHorizontal, int minVertical) {
  cv::Mat h, v;
  cv::morphologyEx(ink, h, cv::MORPH_OPEN, cv::getStructuringElement(cv::MORPH_RECT, {minHorizontal, 1}));
  cv::morphologyEx(ink, v, cv::MORPH_OPEN, cv::getStructuringElement(cv::MORPH_RECT, {1, minVertical}));
  cv::Mat lines = h | v;
  // Thicken slightly so anti-aliased edges of the rules go too.
  cv::dilate(lines, lines, cv::getStructuringElement(cv::MORPH_RECT, {3, 3}));
  return lines;
}

}  // namespace ps::imaging
