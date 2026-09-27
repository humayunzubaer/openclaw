// UTF-8 helpers for Bengali/Latin text post-processing.
#pragma once

#include <string>

namespace ps::text {

std::u32string decode(const std::string& utf8);
std::string encode(const std::u32string& s);

inline bool isBengaliDigit(char32_t c) { return c >= U'০' && c <= U'৯'; }
inline bool isLatinDigit(char32_t c) { return c >= U'0' && c <= U'9'; }
inline bool isDigit(char32_t c) { return isBengaliDigit(c) || isLatinDigit(c); }
inline bool isNumericPunct(char32_t c) {
  return c == U',' || c == U'.' || c == U'/' || c == U'-' || c == U':' || c == U'%';
}

struct DigitProfile {
  int bengali = 0, latin = 0, punct = 0, other = 0;
  int digits() const { return bengali + latin; }
  int total() const { return bengali + latin + punct + other; }
  // Only digits and number punctuation: amounts, dates, BIN, references.
  bool numberLike() const { return digits() >= 1 && other == 0; }
  bool hasAscii = false;  // any Latin letter/digit/bracket (a hint the word may be English)
};

DigitProfile profile(const std::string& utf8);

// Trims whitespace and control characters Tesseract leaves around text.
std::string trim(const std::string& s);

}  // namespace ps::text
