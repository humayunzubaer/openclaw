#include "tables.hpp"

#include <algorithm>
#include <cmath>
#include <map>

#include <opencv2/imgproc.hpp>

namespace ps::tables {

namespace {

struct UnionFind {
  std::vector<int> parent;
  explicit UnionFind(size_t n) : parent(n) {
    for (size_t i = 0; i < n; ++i) parent[i] = static_cast<int>(i);
  }
  int find(int x) { return parent[x] == x ? x : parent[x] = find(parent[x]); }
  void join(int a, int b) { parent[find(a)] = find(b); }
};

double overlap(int a0, int a1, int b0, int b1) { return std::max(0, std::min(a1, b1) - std::max(a0, b0)); }

// Rows and columns follow the grid's topology, not global coordinates: two
// cells share a row when they sit side by side across one rule and their
// heights mostly overlap. This follows rows along a curled page, where a
// global y-sort would chain neighbouring rows together.
void assignRowsAndColumns(DetectedTable& table, double textHeight) {
  auto& cells = table.cells;
  const size_t n = cells.size();
  const int gap = static_cast<int>(std::max(12.0, 1.2 * textHeight));
  UnionFind rows(n), cols(n);
  for (size_t i = 0; i < n; ++i) {
    const cv::Rect& a = cells[i].box;
    for (size_t j = i + 1; j < n; ++j) {
      const cv::Rect& b = cells[j].box;
      const double v = overlap(a.y, a.y + a.height, b.y, b.y + b.height);
      const double h = overlap(a.x, a.x + a.width, b.x, b.x + b.width);
      const bool sideBySide = std::abs(b.x - (a.x + a.width)) <= gap || std::abs(a.x - (b.x + b.width)) <= gap;
      const bool stacked = std::abs(b.y - (a.y + a.height)) <= gap || std::abs(a.y - (b.y + b.height)) <= gap;
      if (sideBySide && v >= 0.6 * std::max(a.height, b.height)) rows.join(static_cast<int>(i), static_cast<int>(j));
      if (stacked && h >= 0.6 * std::max(a.width, b.width)) cols.join(static_cast<int>(i), static_cast<int>(j));
    }
  }
  // Number groups by their mean position.
  auto number = [&](UnionFind& uf, bool vertical, int& count) {
    std::map<int, std::pair<double, int>> acc;  // root -> (sum of centers, count)
    for (size_t i = 0; i < n; ++i) {
      const cv::Rect& r = cells[i].box;
      auto& e = acc[uf.find(static_cast<int>(i))];
      e.first += vertical ? r.y + r.height / 2.0 : r.x + r.width / 2.0;
      e.second += 1;
    }
    std::vector<std::pair<double, int>> order;
    for (auto& [root, e] : acc) order.emplace_back(e.first / e.second, root);
    std::sort(order.begin(), order.end());
    std::map<int, int> index;
    for (size_t k = 0; k < order.size(); ++k) index[order[k].second] = static_cast<int>(k);
    count = static_cast<int>(order.size());
    return index;
  };
  const auto rowIndex = number(rows, true, table.rows);
  const auto colIndex = number(cols, false, table.cols);
  for (size_t i = 0; i < n; ++i) {
    cells[i].row = rowIndex.at(rows.find(static_cast<int>(i)));
    cells[i].col = colIndex.at(cols.find(static_cast<int>(i)));
  }
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
      if (hs.at<int>(k, cv::CC_STAT_AREA) < 0.5 * w * h) continue;
      table.cells.push_back({cv::Rect(x + grid.x, y + grid.y, w, h), 0, 0});
    }
    // A single enclosed box is a framed paragraph, not a table: leave it to
    // the running-text pass.
    if (table.cells.size() < 2) continue;
    // A frame with a small box inside (an ID card with its photo slot) is
    // not a table: real grids are mostly made of cells.
    double cellArea = 0;
    for (auto& c : table.cells) cellArea += c.box.area();
    if (cellArea < 0.5 * grid.area()) continue;

    assignRowsAndColumns(table, textHeight);
    std::sort(table.cells.begin(), table.cells.end(),
              [](auto& a, auto& b) { return a.row != b.row ? a.row < b.row : a.col < b.col; });
    tables.push_back(std::move(table));
  }
  std::sort(tables.begin(), tables.end(), [](auto& a, auto& b) { return a.box.y < b.box.y; });
  return tables;
}

}  // namespace ps::tables
