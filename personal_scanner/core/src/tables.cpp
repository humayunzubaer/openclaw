#include "tables.hpp"

#include <algorithm>
#include <cmath>

#include <opencv2/imgproc.hpp>

namespace ps::tables {

namespace {

// Groups 1-D values into clusters no wider than `tol`; returns the index of
// each value's cluster, clusters ordered by position.
std::vector<int> cluster(const std::vector<double>& values, double tol) {
  std::vector<int> order(values.size());
  for (size_t i = 0; i < order.size(); ++i) order[i] = static_cast<int>(i);
  std::sort(order.begin(), order.end(), [&](int a, int b) { return values[a] < values[b]; });
  std::vector<int> label(values.size(), 0);
  int current = -1;
  double anchor = -1e18;
  for (int idx : order) {
    if (values[idx] - anchor > tol) {
      ++current;
      anchor = values[idx];
    }
    label[idx] = current;
  }
  return label;
}

}  // namespace

std::vector<DetectedTable> detect(const cv::Mat& lines, double textHeight) {
  std::vector<DetectedTable> tables;
  const double minCell = std::max(8.0, 0.8 * textHeight);

  cv::Mat labels, stats, centroids;
  const int n = cv::connectedComponentsWithStats(lines, labels, stats, centroids, 8);
  for (int i = 1; i < n; ++i) {
    const cv::Rect grid(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
                        stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
    if (grid.width < 0.15 * lines.cols || grid.height < 1.5 * textHeight) continue;

    // Cells are the background regions fully enclosed by this grid's rules.
    cv::Mat own = (labels(grid) == i);
    cv::Mat holes;
    cv::bitwise_not(own, holes);
    cv::Mat hl, hs, hc;
    const int m = cv::connectedComponentsWithStats(holes, hl, hs, hc, 4);
    DetectedTable table;
    table.box = grid;
    for (int k = 1; k < m; ++k) {
      const int x = hs.at<int>(k, cv::CC_STAT_LEFT), y = hs.at<int>(k, cv::CC_STAT_TOP);
      const int w = hs.at<int>(k, cv::CC_STAT_WIDTH), h = hs.at<int>(k, cv::CC_STAT_HEIGHT);
      const bool touchesEdge = x == 0 || y == 0 || x + w >= grid.width || y + h >= grid.height;
      if (touchesEdge || w < minCell || h < minCell) continue;
      // Enclosed but mostly empty of its bounding box => not a rectangular cell.
      if (hs.at<int>(k, cv::CC_STAT_AREA) < 0.6 * w * h) continue;
      table.cells.push_back({cv::Rect(x + grid.x, y + grid.y, w, h), 0, 0});
    }
    // A single enclosed box is a framed paragraph, not a table: leave it to
    // the running-text pass.
    if (table.cells.size() < 2) continue;

    std::vector<double> ys, xs;
    double minH = 1e9, minW = 1e9;
    for (auto& c : table.cells) {
      ys.push_back(c.box.y);
      xs.push_back(c.box.x);
      minH = std::min<double>(minH, c.box.height);
      minW = std::min<double>(minW, c.box.width);
    }
    const auto rowOf = cluster(ys, 0.5 * minH);
    const auto colOf = cluster(xs, std::max(6.0, 0.3 * minW));
    for (size_t k = 0; k < table.cells.size(); ++k) {
      table.cells[k].row = rowOf[k];
      table.cells[k].col = colOf[k];
      table.rows = std::max(table.rows, rowOf[k] + 1);
      table.cols = std::max(table.cols, colOf[k] + 1);
    }
    std::sort(table.cells.begin(), table.cells.end(),
              [](auto& a, auto& b) { return a.row != b.row ? a.row < b.row : a.col < b.col; });
    tables.push_back(std::move(table));
  }
  std::sort(tables.begin(), tables.end(), [](auto& a, auto& b) { return a.box.y < b.box.y; });
  return tables;
}

}  // namespace ps::tables
