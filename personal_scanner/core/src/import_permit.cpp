#include "ps/import_permit.hpp"

#include <cmath>
#include <cstdlib>
#include <regex>
#include <sstream>

namespace ps::permit {

namespace {

std::string escape(const std::string& s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') o += '\\';
    if (static_cast<unsigned char>(c) >= 0x20) o += c;
  }
  return o;
}

std::string firstMatch(const std::string& text, const std::regex& re, int group = 1) {
  std::smatch m;
  return std::regex_search(text, m, re) ? m[group].str() : "";
}

// OCR reads the letter O for zero inside reference codes (HBKLIBLO1).
// Codes on this form never put the letter O next to a digit.
std::string fixCodeZeros(std::string code) {
  for (size_t i = 0; i < code.size(); ++i) {
    if (code[i] != 'O') continue;
    const bool digitBefore = i > 0 && std::isdigit(static_cast<unsigned char>(code[i - 1]));
    const bool digitAfter = i + 1 < code.size() && std::isdigit(static_cast<unsigned char>(code[i + 1]));
    if (digitBefore || digitAfter) code[i] = '0';
  }
  return code;
}

// Amount "86,265.00" -> cents. Returns -1 when not an amount.
long long cents(const std::string& s) {
  std::string d;
  for (char c : s) {
    if (std::isdigit(static_cast<unsigned char>(c))) d += c;
    else if (c != ',' && c != '.') return -1;
  }
  if (d.size() < 3 || s.size() < 4 || s[s.size() - 3] != '.') return -1;
  return std::atoll(d.c_str());
}

std::string formatCents(long long c) {
  std::string whole = std::to_string(c / 100);
  for (int i = static_cast<int>(whole.size()) - 3; i > 0; i -= 3) whole.insert(i, ",");
  char frac[4];
  std::snprintf(frac, sizeof frac, "%02lld", c % 100);
  return whole + "." + frac;
}

// Weight "1197.19" / "24.0" -> hundredths, keeping the printed precision.
bool parseWeight(const std::string& s, long long& hundredths, int& decimals) {
  const auto dot = s.find('.');
  if (dot == std::string::npos || s.find_first_not_of("0123456789.") != std::string::npos) return false;
  decimals = static_cast<int>(s.size() - dot - 1);
  if (decimals < 1 || decimals > 2) return false;
  hundredths = std::atoll(s.substr(0, dot).c_str()) * 100 + std::atoll(s.substr(dot + 1).c_str()) * (decimals == 1 ? 10 : 1);
  return true;
}

std::string formatWeight(long long h, int decimals) {
  std::string out = std::to_string(h / 100) + ".";
  if (decimals == 1) return out + std::to_string((h % 100) / 10);
  char frac[4];
  std::snprintf(frac, sizeof frac, "%02lld", h % 100);
  return out + frac;
}

// Digits that print/scan alike; a single such swap is a plausible OCR error.
bool confusable(char a, char b) {
  static const char* pairs[] = {"58", "38", "68", "08", "17", "69", "35", "56"};
  for (auto p : pairs)
    if ((a == p[0] && b == p[1]) || (a == p[1] && b == p[0])) return true;
  return false;
}

// Same length and exactly one differing digit, and that digit pair is a
// known look-alike.
bool oneConfusableDigit(const std::string& a, const std::string& b) {
  if (a.size() != b.size()) return false;
  int diff = 0;
  for (size_t i = 0; i < a.size(); ++i) {
    if (a[i] == b[i]) continue;
    if (++diff > 1 || !confusable(a[i], b[i])) return false;
  }
  return diff == 1;
}

}  // namespace

bool looksLikeImportPermit(const std::string& text) {
  static const std::regex re(R"(Import Permit|Permit Details|Permit No|Permited Till|Permitted by BEPZA)", std::regex::icase);
  return std::regex_search(text, re);
}

ImportPermit extract(const std::string& raw) {
  ImportPermit p;
  p.detected = looksLikeImportPermit(raw);
  if (!p.detected) return p;

  // Flatten to one line: two-column layouts split "label : value" across lines.
  std::string t = std::regex_replace(raw, std::regex(R"(\s+)"), " ");
  // OCR reads ":" separators as typographic marks; std::regex works on bytes,
  // so map these multi-byte characters to ASCII first.
  for (const char* mark : {"\xC2\xBB", "\xC2\xAB", "\xE2\x80\x98", "\xE2\x80\x99", "\xE2\x80\x9C", "\xE2\x80\x9D", "\xE2\x80\x94"})
    t = std::regex_replace(t, std::regex(mark), ":");
  auto& f = p.fields;
  const auto icase = std::regex::icase;

  // Permit number: "ID" + 10 digits whose first six are the permit date
  // (ddmmyy). OCR renders "ID" as 1D, lD, |D or 10; the barcode caption
  // repeats the number.
  const std::regex permitRe(R"((?:ID|[1Il|][D0O])\s?(\d{10}))");
  std::vector<std::string> permitDigits;
  for (auto it = std::sregex_iterator(t.begin(), t.end(), permitRe); it != std::sregex_iterator(); ++it)
    permitDigits.push_back((*it)[1].str());
  {
    // The date can wrap across a line break: "14- 03-2026".
    std::smatch m;
    if (std::regex_search(t, m, std::regex(R"(Permit date\W*(\d{2}) ?- ?(\d{2}) ?- ?(\d{4}))", icase)))
      f["permit_date"] = m[1].str() + "-" + m[2].str() + "-" + m[3].str();
  }
  if (!permitDigits.empty()) {
    std::string chosen = permitDigits.front();
    const std::string& d = f["permit_date"];
    const std::string ddmmyy = d.size() == 10 ? d.substr(0, 2) + d.substr(3, 2) + d.substr(8, 2) : "";
    for (auto& c : permitDigits)
      if (!ddmmyy.empty() && c.compare(0, 6, ddmmyy) == 0) { chosen = c; break; }
    f["permit_no"] = "ID" + chosen;
    if (!ddmmyy.empty() && chosen.compare(0, 6, ddmmyy) != 0)
      p.issues.push_back({"permit_no", "permit number does not encode the permit date (ddmmyy)", "", false});
    for (auto& c : permitDigits)
      if (c != chosen) p.issues.push_back({"permit_no", "barcode caption and header disagree: " + c, "", false});
  }

  // Values in capitals end where the next label (Capitalized word) starts.
  const std::string caps = R"(([A-Z|1][A-Z0-9,.\-]*(?: [A-Z0-9,.\-]+)*?)(?= [A-Z][a-z]| \W| *$))";
  f["company"] = firstMatch(t, std::regex(R"(\w*me o\w Company\W*(.+?)\s+(?:Zon\w|Source))", icase));
  f["company"] = std::regex_replace(f["company"], std::regex(R"(\bL[i1l]d\b)"), "Ltd");
  f["source_country"] = firstMatch(t, std::regex(R"(Source Country\W*)" + caps));
  f["place_of_load"] = firstMatch(t, std::regex(R"(Place of Load\W*)" + caps));
  f["bl_no"] = firstMatch(t, std::regex(R"(Bill, ?T\.?C\W*([A-Z0-9]{2,}))"));
  f["place_of_unload"] = firstMatch(t, std::regex(R"(Place of Unload\W*)" + caps));
  // "IEPZ" (Ishwardi EPZ): the capital I is read as 1 or |.
  f["place_of_unload"] = std::regex_replace(f["place_of_unload"], std::regex(R"(^[1|l]EPZ$)"), "IEPZ");
  f["undertaking_no"] = fixCodeZeros(firstMatch(t, std::regex(R"(Under Taking No\W*([A-Z0-9][A-Z0-9/\-]{5,}))", icase)));
  f["undertaking_date"] = firstMatch(t, std::regex(R"(Under Taking\s*[^\w\s]{0,4}\s*(\d{2}/\d{2}/\d{4}))", icase));
  f["invoice_no"] = fixCodeZeros(firstMatch(t, std::regex(R"(Invoice No\W*([A-Z0-9][A-Za-z0-9/\-]{3,}))", icase)));
  f["invoice_date"] = firstMatch(t, std::regex(R"(Invoice Date\W*(\d{2}/\d{2}/\d{4}))", icase));
  f["permitted_till"] = firstMatch(t, std::regex(R"(Permit+ed Till\W*(\d{2}/\d{2}/\d{4}))", icase));
  f["invoice_value"] = firstMatch(t, std::regex(R"(Inv\w+ Value\W*(\d[\d,]*\.\d{2}))", icase));
  f["total_net_weight"] = firstMatch(t, std::regex(R"(Total Net Weight\W*(\d+\.\d+))", icase));
  f["lc_no"] = fixCodeZeros(firstMatch(t, std::regex(R"(LC No\W+(?:T\W*T\W*P\W*)?([A-Z0-9][A-Z0-9/\-]{5,}))", icase)));
  f["lc_issue"] = firstMatch(t, std::regex(R"(Issue\W*(\d{2}-\d{2}-\d{4}))", icase));
  f["bank"] = firstMatch(t, std::regex(R"(O\w Bank\W*([A-Z][A-Za-z .]*?(?:Limited|Ltd\.?)))", icase));
  f["supplier"] = firstMatch(t, std::regex(R"(Supp\w+ Name\W*(.+?)\s+Inv\w+ Value)", icase));

  // Line items: HS code (8 digits), quantity + unit, net weight, FOB US$, FOB USD.
  const std::regex itemRe(
      // Quantity may lose its leading digit (".0 Nos"); amounts must end on
      // two decimals, not run into a split "2.400 00".
      R"(\b(\d{8})\s+([\d.,]*\d)\s*([A-Za-z]{2,5})\b[\W_]*(\d[\d.]*)\s+(\d[\d,]*\.\d{2})(?![\d])\W*(\d[\d,]*\.\d{2}(?![\d]))?)");
  for (auto it = std::sregex_iterator(t.begin(), t.end(), itemRe); it != std::sregex_iterator(); ++it) {
    const auto& m = *it;
    Item item{m[1], m[2], m[3], m[4], m[6].matched ? m[6].str() : m[5].str()};
    // Same amount in both columns but one lost its thousands comma: keep the
    // formatted one.
    if (m[6].matched && cents(m[5]) == cents(m[6]) && m[5].str().find(',') != std::string::npos) item.fob = m[5];
    if (m[6].matched && cents(m[5]) != cents(m[6])) {
      // The two FOB columns carry the same amount; keep the one that is a
      // well-formed amount and note the disagreement.
      p.issues.push_back({"fob", "FOB columns differ for HS " + item.hsCode + ": " + m[5].str() + " vs " + m[6].str(), "", false});
    }
    p.items.push_back(item);
  }

  // Invoice value vs FOB column. Each item amount is printed twice, the
  // invoice value once, so the items are the stronger evidence.
  if (!p.items.empty() && !f["invoice_value"].empty()) {
    long long sum = 0;
    bool ok = true;
    for (auto& it : p.items) {
      const long long c = cents(it.fob);
      if (c < 0) { ok = false; break; }
      sum += c;
    }
    const long long invoice = cents(f["invoice_value"]);
    if (ok && invoice >= 0 && sum != invoice) {
      const std::string expected = formatCents(sum);
      if (oneConfusableDigit(expected, f["invoice_value"])) {
        p.issues.push_back({"invoice_value", "read " + f["invoice_value"] + ", FOB items total " + expected, expected, true});
        f["invoice_value"] = expected;
      } else {
        p.issues.push_back({"invoice_value", "does not equal FOB items total " + expected, expected, false});
      }
    }
  }

  // Net weights vs Total Net Weight: one line off by a look-alike digit is
  // corrected from the total.
  if (!p.items.empty() && !f["total_net_weight"].empty()) {
    long long total = 0, sum = 0;
    int totalDec = 0;
    std::vector<long long> w(p.items.size());
    std::vector<int> dec(p.items.size());
    bool ok = parseWeight(f["total_net_weight"], total, totalDec);
    for (size_t i = 0; ok && i < p.items.size(); ++i) {
      ok = parseWeight(p.items[i].netWeight, w[i], dec[i]);
      sum += w[i];
    }
    if (ok && sum != total) {
      // Correct only when exactly one line can explain the difference; if
      // several could (e.g. 126.8 -> 126.5 and 257.8 -> 257.5 both close the
      // gap), guessing would risk corrupting a correct value.
      std::vector<std::pair<size_t, std::string>> candidates;
      for (size_t i = 0; i < p.items.size(); ++i) {
        const long long implied = total - (sum - w[i]);
        if (implied <= 0) continue;
        const std::string candidate = formatWeight(implied, dec[i]);
        if (oneConfusableDigit(candidate, p.items[i].netWeight)) candidates.emplace_back(i, candidate);
      }
      if (candidates.size() == 1) {
        auto& [i, candidate] = candidates.front();
        p.issues.push_back({"net_weight", "HS " + p.items[i].hsCode + " read " + p.items[i].netWeight + ", total implies " + candidate, candidate, true});
        p.items[i].netWeight = candidate;
      } else {
        std::string msg = "net weights do not add up to the total";
        for (auto& [i, c] : candidates) msg += "; HS " + p.items[i].hsCode + " may be " + c;
        p.issues.push_back({"total_net_weight", msg, "", false});
      }
    }
  }

  // Years: reference codes and dates should sit near the permit year.
  const std::string& pd = f["permit_date"];
  if (pd.size() == 10) {
    const int year = std::atoi(pd.substr(6).c_str());
    const std::regex yearRe(R"(/(20\d\d)/)");
    std::string& ut = f["undertaking_no"];
    std::smatch m;
    if (std::regex_search(ut, m, yearRe)) {
      const std::string y = m[1];
      const int v = std::atoi(y.c_str());
      if (std::abs(v - year) > 1) {
        std::string fix;
        for (int cand = year - 1; cand <= year + 1 && fix.empty(); ++cand)
          if (oneConfusableDigit(std::to_string(cand), y)) fix = std::to_string(cand);
        if (!fix.empty()) {
          const std::string corrected = ut.substr(0, m.position(1)) + fix + ut.substr(m.position(1) + 4);
          p.issues.push_back({"undertaking_no", "year " + y + " is far from permit year; read as " + fix, corrected, true});
          ut = corrected;
        } else {
          p.issues.push_back({"undertaking_no", "year " + y + " is far from permit year", "", false});
        }
      }
    }
  }

  // Dates: the invoice and the undertaking precede the permit; the permit
  // runs out after it is issued. A violation is flagged, not "fixed": a
  // 5/8 slip in a date usually has several plausible readings.
  {
    auto ymd = [](const std::string& d) -> long {
      if (d.size() != 10) return -1;
      return std::atol(d.substr(6, 4).c_str()) * 10000 + std::atol(d.substr(3, 2).c_str()) * 100 +
             std::atol(d.substr(0, 2).c_str());
    };
    const long permit = ymd(f["permit_date"]);
    if (permit > 0) {
      for (const char* key : {"invoice_date", "undertaking_date", "lc_issue"}) {
        const long d = ymd(f[key]);
        if (d > permit) p.issues.push_back({key, std::string(key) + " is after the permit date; check the digits", "", false});
      }
      const long till = ymd(f["permitted_till"]);
      if (till > 0 && till <= permit) p.issues.push_back({"permitted_till", "permitted till is not after the permit date", "", false});
    }
  }

  for (auto it = f.begin(); it != f.end();) it = it->second.empty() ? f.erase(it) : std::next(it);
  return p;
}

std::string ImportPermit::json() const {
  std::ostringstream o;
  o << "{\"detected\":" << (detected ? "true" : "false") << ",\"fields\":{";
  bool first = true;
  for (auto& [k, v] : fields) {
    o << (first ? "" : ",") << '"' << k << "\":\"" << escape(v) << '"';
    first = false;
  }
  o << "},\"items\":[";
  for (size_t i = 0; i < items.size(); ++i) {
    auto& it = items[i];
    o << (i ? "," : "") << "{\"hs\":\"" << escape(it.hsCode) << "\",\"quantity\":\"" << escape(it.quantity)
      << "\",\"unit\":\"" << escape(it.unit) << "\",\"net_weight\":\"" << escape(it.netWeight) << "\",\"fob\":\""
      << escape(it.fob) << "\"}";
  }
  o << "],\"issues\":[";
  for (size_t i = 0; i < issues.size(); ++i) {
    auto& is = issues[i];
    o << (i ? "," : "") << "{\"field\":\"" << escape(is.field) << "\",\"message\":\"" << escape(is.message)
      << "\",\"suggested\":\"" << escape(is.suggested) << "\",\"corrected\":" << (is.corrected ? "true" : "false") << '}';
  }
  o << "]}";
  return o.str();
}

}  // namespace ps::permit
