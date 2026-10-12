// BEPZA Import Permit (Foreign Import / Domestic Tariff Area) extraction.
//
// Pulls the key fields out of an OCR'd permit and cross-checks them using
// the form's own redundancy: permit no. vs barcode text, Invoice Value vs
// the FOB column, Net Weight lines vs Total Net Weight, date sanity. A single
// inconsistent line item is corrected from the totals; anything else is
// flagged for review instead of guessed.
#pragma once

#include <map>
#include <string>
#include <vector>

#include "ps/engine.hpp"

namespace ps::permit {

struct Item {
  std::string hsCode, quantity, unit, netWeight, fob;
};

struct Issue {
  std::string field;
  std::string message;    // English, for logs/UI mapping
  std::string suggested;  // corrected value when the form's arithmetic determines it
  bool corrected = false; // true: `suggested` was applied to the field
};

struct ImportPermit {
  bool detected = false;
  std::map<std::string, std::string> fields;
  std::vector<Item> items;
  std::vector<Issue> issues;
  std::string json() const;
};

// True when the page text looks like a BEPZA import permit.
bool looksLikeImportPermit(const std::string& pageText);

ImportPermit extract(const std::string& pageText);

}  // namespace ps::permit
