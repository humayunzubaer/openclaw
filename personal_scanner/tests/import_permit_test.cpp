// Import Permit extraction tests on synthetic OCR text (no real permit data).
#include <cstdio>
#include <string>

#include "ps/import_permit.hpp"

static int failures = 0;

static void expectEq(const std::string& what, const std::string& got, const std::string& want) {
  if (got != want) {
    std::printf("FAIL %s: got '%s' want '%s'\n", what.c_str(), got.c_str(), want.c_str());
    ++failures;
  }
}

static bool hasIssue(const ps::permit::ImportPermit& p, const std::string& field, bool corrected) {
  for (auto& i : p.issues)
    if (i.field == field && i.corrected == corrected) return true;
  return false;
}

int main() {
  // Typical OCR output: "ID" read as "1D", "O" for zero, a 6/8 slip in the
  // invoice value, a 5/8 slip in the undertaking year, "»" for ":".
  const std::string page =
      "Import Permit Details - Foreign Import\n"
      "For Permit No: 1D0102270007, Permit date: 01-02-2027\n"
      "*1D0102270007*\n"
      "Name of Company : Example Textiles BD Lid Zone : Test Export Processing Zone\n"
      "Source Zone : Source Country : CHINA\n"
      "Place of Load : NANSHA Type of Carrier : Sea\n"
      "B/L.AW Bill, T.C : ABCD12345 Place of Unload : 1EPZ Under Taking : 30/01/2027\n"
      "Under Taking No. : EX/2021/BZA-U/01/26-27\n"
      "Invoice No : INVO7 Invoice Date » 15/01/2027 Permited Till : 01/03/2027\n"
      "Supplier Name : SAMPLE TRADING CO.LTD. Invoice Value : 6,500.00\n"
      "Product Description HS Code Quantity Net Weight\n"
      "cotton fabric 52083200 1000.0 KG 1000.0 6,000.00 6,000.00\n"
      "buttons 96062100 10.0 Pcs 12.5 2,500.00 2,500.00\n"
      "Total Net Weight 1012.5\n"
      "LC No. /TT/P. : LC/EX/26-27/0O9 Type : Sales Contract Issue : 10-01-2027\n"
      "Name Of Bank : Sample Bank Limited\n";

  const auto p = ps::permit::extract(page);
  expectEq("detected", p.detected ? "yes" : "no", "yes");
  expectEq("permit_no", p.fields.at("permit_no"), "ID0102270007");
  expectEq("permit_date", p.fields.at("permit_date"), "01-02-2027");
  expectEq("company", p.fields.at("company"), "Example Textiles BD Ltd");
  expectEq("place_of_unload", p.fields.at("place_of_unload"), "IEPZ");
  expectEq("invoice_no", p.fields.at("invoice_no"), "INV07");
  expectEq("invoice_date", p.fields.at("invoice_date"), "15/01/2027");
  expectEq("lc_no", p.fields.at("lc_no"), "LC/EX/26-27/009");
  expectEq("bank", p.fields.at("bank"), "Sample Bank Limited");
  expectEq("items", std::to_string(p.items.size()), "2");
  // 6,000 + 2,500 = 8,500; "6,500.00" differs by one look-alike digit.
  expectEq("invoice_value", p.fields.at("invoice_value"), "8,500.00");
  if (!hasIssue(p, "invoice_value", true)) { std::printf("FAIL invoice_value correction not reported\n"); ++failures; }
  // 2021 is far from 2027; 2027 is one look-alike swap away (1/7).
  expectEq("undertaking_no", p.fields.at("undertaking_no"), "EX/2027/BZA-U/01/26-27");

  // Two lines could each close the net-weight gap: flag, never guess.
  const std::string ambiguous =
      "Import Permit Details Permit No: ID0102270007, Permit date: 01-02-2027 "
      "a 11111111 1.0 Pcs 126.8 10.00 10.00 b 22222222 1.0 Pcs 257.8 20.00 20.00 Total Net Weight 384.3";
  const auto q = ps::permit::extract(ambiguous);
  expectEq("ambiguous nw_1", q.items.at(0).netWeight, "126.8");
  expectEq("ambiguous nw_2", q.items.at(1).netWeight, "257.8");
  if (!hasIssue(q, "total_net_weight", false)) { std::printf("FAIL ambiguous weights not flagged\n"); ++failures; }

  std::printf(failures ? "%d failure(s)\n" : "all import permit tests passed\n", failures);
  return failures ? 1 : 0;
}
