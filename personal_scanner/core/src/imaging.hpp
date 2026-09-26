// Image cleanup stages. Each is independent and deterministic so the
// benchmark can attribute accuracy changes to a single stage.
#pragma once

#include <optional>
#include <vector>

#include <opencv2/core.hpp>

namespace ps::imaging {

cv::Mat toGray(const cv::Mat& image);

// Finds the sheet of paper in a photo. Returns its 4 corners (tl, tr, br, bl)
// or nothing when the image is already a flat scan / no clear sheet exists.
std::optional<std::vector<cv::Point2f>> findPage(const cv::Mat& gray);

// Warps the quad to a rectangle whose aspect ratio follows the quad sides.
cv::Mat warpPage(const cv::Mat& image, const std::vector<cv::Point2f>& quad);

// Removes shadows and uneven lighting: divides by an estimate of the paper
// background so paper becomes ~white and ink keeps its contrast.
cv::Mat flattenIllumination(const cv::Mat& gray);

// Ink mask (255 = ink) from a flattened page.
cv::Mat binarize(const cv::Mat& flat);

// Dominant text-line angle in degrees (positive = counter-clockwise), found
// by maximizing the row-projection sharpness of the ink mask.
double estimateSkew(const cv::Mat& ink, double maxDegrees = 8.0);

cv::Mat rotate(const cv::Mat& image, double degrees, int borderValue);

// True when text lines run vertically (page photographed sideways). Up/down
// cannot be told from geometry alone; the engine settles it by OCR confidence.
bool isSideways(const cv::Mat& ink);
cv::Mat rotateQuarterTurns(const cv::Mat& image, int turns);

// Median height of glyph clusters, used to bring text to the size the
// Tesseract LSTM models were trained on.
double medianTextHeight(const cv::Mat& ink);

// Horizontal and vertical ruling lines (form boxes, table grids, underlines).
// Horizontal rules must be far longer than a word: the Bengali headline
// (matra) is itself a horizontal stroke spanning the whole word.
cv::Mat rulingLines(const cv::Mat& ink, int minHorizontal, int minVertical);

}  // namespace ps::imaging
