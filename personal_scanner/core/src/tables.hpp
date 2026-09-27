// Ruled-table detection: finds grids in the ruling-line mask and returns
// their cells in row/column order.
#pragma once

#include <vector>

#include <opencv2/core.hpp>

namespace ps::tables {

struct DetectedCell {
  cv::Rect box;
  int row = 0, col = 0;
};

struct DetectedTable {
  cv::Rect box;
  std::vector<DetectedCell> cells;
  int rows = 0, cols = 0;
};

// `lines` is the ruling-line mask (255 = rule). `textHeight` is the median
// glyph height, used to reject slivers between double rules.
std::vector<DetectedTable> detect(const cv::Mat& lines, double textHeight);

}  // namespace ps::tables
