// Personal Scanner OCR core: offline Bengali document recognition.
//
// Pipeline: page detection -> perspective correction -> illumination
// flattening -> deskew -> scale normalization -> ruling-line removal ->
// table/cell detection -> Tesseract LSTM per region -> numeric re-reads.
//
// The same code runs on Android/iOS (through the C API in ps/c_api.h) and on
// desktop for benchmarking (tools/ps_ocr.cpp).
#pragma once

#include <memory>
#include <string>
#include <vector>

#include <opencv2/core.hpp>

namespace ps {

struct Options {
  std::string tessdataDir;          // folder holding ben.traineddata (and eng)
  std::string languages = "ben";    // main model; Bengali digits and text
  std::string latinLanguage = "eng";  // fallback for English words; empty disables
  std::string debugDir;             // non-empty: dump intermediate images here
  bool detectPage = true;           // find the sheet in a photo and flatten it
  bool detectTables = true;         // OCR grid tables cell by cell
  bool numericRereads = true;       // re-read digit-like words with a digit whitelist
};

struct Line {
  std::string text;
  float confidence = 0;  // 0..100, mean over words
  cv::Rect box;          // in normalized page coordinates
};

struct Cell {
  int row = 0, col = 0;
  std::string text;
  float confidence = 0;
  cv::Rect box;
};

struct Block {
  enum class Kind { Text, Table } kind = Kind::Text;
  cv::Rect box;
  std::vector<Line> lines;  // Kind::Text
  std::vector<Cell> cells;  // Kind::Table
  int rows = 0, cols = 0;
};

struct Page {
  std::vector<Block> blocks;  // reading order (top to bottom)
  cv::Mat normalized;         // the cleaned page image OCR ran on
  double skewDegrees = 0;
  double scale = 1;
  bool pageFound = false;
  std::string script;  // "bengali" or "latin": the model the page was read with

  // Plain text: one line per text line / table row, table cells tab-separated.
  std::string text() const;
  // Machine-readable result with boxes and confidences.
  std::string json() const;
};

class Engine {
 public:
  explicit Engine(Options options);
  ~Engine();
  Engine(const Engine&) = delete;
  Engine& operator=(const Engine&) = delete;

  Page recognize(const cv::Mat& image);

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace ps
