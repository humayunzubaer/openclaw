#include "text.hpp"

#include <cctype>

namespace ps::text {

std::u32string decode(const std::string& s) {
  std::u32string out;
  out.reserve(s.size());
  for (size_t i = 0; i < s.size();) {
    const unsigned char c = s[i];
    char32_t cp;
    int len;
    if (c < 0x80) { cp = c; len = 1; }
    else if ((c >> 5) == 0x6) { cp = c & 0x1F; len = 2; }
    else if ((c >> 4) == 0xE) { cp = c & 0x0F; len = 3; }
    else if ((c >> 3) == 0x1E) { cp = c & 0x07; len = 4; }
    else { ++i; continue; }  // stray continuation byte
    if (i + len > s.size()) break;
    for (int k = 1; k < len; ++k) cp = (cp << 6) | (static_cast<unsigned char>(s[i + k]) & 0x3F);
    out.push_back(cp);
    i += len;
  }
  return out;
}

std::string encode(const std::u32string& s) {
  std::string out;
  out.reserve(s.size() * 3);
  for (char32_t c : s) {
    if (c < 0x80) out.push_back(static_cast<char>(c));
    else if (c < 0x800) {
      out.push_back(static_cast<char>(0xC0 | (c >> 6)));
      out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
    } else if (c < 0x10000) {
      out.push_back(static_cast<char>(0xE0 | (c >> 12)));
      out.push_back(static_cast<char>(0x80 | ((c >> 6) & 0x3F)));
      out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
    } else {
      out.push_back(static_cast<char>(0xF0 | (c >> 18)));
      out.push_back(static_cast<char>(0x80 | ((c >> 12) & 0x3F)));
      out.push_back(static_cast<char>(0x80 | ((c >> 6) & 0x3F)));
      out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
    }
  }
  return out;
}

DigitProfile profile(const std::string& utf8) {
  DigitProfile p;
  for (char32_t c : decode(utf8)) {
    if (c == U' ') continue;
    if (c < 0x80 && (std::isalnum(static_cast<int>(c)) || c == U'[' || c == U']' || c == U'|')) p.hasAscii = true;
    if (isBengaliDigit(c)) ++p.bengali;
    else if (isLatinDigit(c)) ++p.latin;
    else if (isNumericPunct(c)) ++p.punct;
    else ++p.other;
  }
  return p;
}

std::string trim(const std::string& s) {
  size_t b = 0, e = s.size();
  while (b < e && static_cast<unsigned char>(s[b]) <= 0x20) ++b;
  while (e > b && static_cast<unsigned char>(s[e - 1]) <= 0x20) --e;
  return s.substr(b, e - b);
}

}  // namespace ps::text
