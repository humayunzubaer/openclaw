"""
বিয়োজনের শর্তে আমদানি প্রাপ্যতা — ঊর্ধ্বসীমা যাচাই regression test.

চালান:  python3 tests/test_provisional_entitlement.py

যাচাই করে:
  • ০১.০৭.২০২৬ এর পূর্বে সীমা = সম্ভাব্য প্রাপ্যতা ÷ ৩; উক্ত তারিখ ও পরে ÷ ৪
  • সীমাতিরিক্ত সাময়িক প্রাপ্যতা আর আমদানির ঢাল নহে → দাবি ২ বাড়ে
  • সীমার মধ্যে থাকিলে পূর্বের আচরণ অপরিবর্তিত (regression)
  • লঙ্ঘনে দাবিনামা জারির প্রস্তাব ও সতর্কবার্তা আসে
  • পৃথক নূতন দাবি তৈরি হয় না (দ্বৈত গণনা রোধ)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow

CLAIM2 = "দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)"
GRAND = "সর্বমোট রাজস্ব দাবি (BDT)"
_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def _period():
    return dict(period_from=date(2025, 1, 1), period_to=date(2025, 12, 31))


def _run(taken, probable, ref_date, imported=None):
    """base 1000 + সাময়িক `taken`; সম্ভাব্য প্রাপ্যতা `probable`।"""
    ent = [EntitlementRow(
        row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON YARN",
        entitled_quantity=1000.0, extended_entitlement=taken,
        next_period_probable=probable, unit="KG", **_period())]
    imp = [ImportRow(
        row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
        hs_code="5205.11.00", item_name="COTTON YARN",
        quantity=imported if imported is not None else 0.0, unit="KG",
        value_bdt=1_000_000, duty_paid=100_000, vat_paid=150_000)]
    return ImportAnalysisEngine(
        ent, imp, provisional_entitlement_date=ref_date).analyze()


def case_old_regime_divisor():
    print("CASE 1 — ০১.০৭.২০২৬ এর পূর্বে: সীমা = সম্ভাব্য ÷ ৩")
    # সম্ভাব্য 60,000 → সীমা 20,000; গৃহীত 25,000 → অতিরিক্ত 5,000
    res = _run(taken=25000, probable=60000, ref_date=date(2026, 6, 30), imported=1500)
    rec = res.provisional_records
    check("1 provisional record", len(rec) == 1)
    check("divisor label = এক-তৃতীয়াংশ", bool(rec) and "এক-তৃতীয়াংশ" in rec[0].divisor_label)
    check("cap = 20,000", bool(rec) and abs(rec[0].allowed_cap - 20000) < 0.01)
    check("excess = 5,000", bool(rec) and abs(rec[0].excess_quantity - 5000) < 0.01)
    check("status = সীমা অতিক্রম", bool(rec) and rec[0].status == "সীমা অতিক্রম")
    check("দাবিনামা প্রস্তাব উপস্থিত", bool(rec) and "দাবিনামা" in rec[0].demand_proposal)
    check("সতর্কবার্তা আসে", any("বিয়োজনের শর্তে" in w for w in res.warnings))
    check("summary: সীমা অতিক্রম = 1",
          res.summary["বিয়োজনের শর্তে প্রাপ্যতা — সীমা অতিক্রম"] == 1)


def case_new_regime_divisor():
    print("CASE 2 — ০১.০৭.২০২৬ ও তৎপরবর্তী: সীমা = সম্ভাব্য ÷ ৪")
    res = _run(taken=25000, probable=60000, ref_date=date(2026, 7, 1), imported=1500)
    rec = res.provisional_records[0]
    check("divisor label = এক-চতুর্থাংশ", "এক-চতুর্থাংশ" in rec.divisor_label)
    check("cap = 15,000", abs(rec.allowed_cap - 15000) < 0.01)
    check("excess = 10,000", abs(rec.excess_quantity - 10000) < 0.01)


def case_excess_no_longer_shields():
    print("CASE 3 — সীমাতিরিক্ত সাময়িক প্রাপ্যতা আর ঢাল নহে (দাবি ২ বাড়ে)")
    # base 1000 + গৃহীত 900; সম্ভাব্য 1200 → সীমা (÷৩) 400 → বৈধ ceiling = 1400
    # আমদানি 1500 → অতিরিক্ত 100 (সীমা প্রয়োগ না হইলে ceiling 1900 হইত, অতিরিক্ত 0)
    res = _run(taken=900, probable=1200, ref_date=date(2026, 6, 30), imported=1500)
    ex = res.excess_records
    check("excess record তৈরি হয়", len(ex) == 1)
    check("ceiling = 1400 (base 1000 + বৈধ 400)",
          bool(ex) and abs(ex[0].entitled_quantity - 1400) < 0.01)
    check("অতিরিক্ত = 100 KG", bool(ex) and abs(ex[0].excess_quantity - 100) < 0.01)
    check("দাবি ২ > 0 (শুল্কায়ন হইয়াছে)", res.summary[CLAIM2] > 0)
    check("পৃথক নূতন দাবি নাই — grand == দাবি ২",
          abs(res.summary[GRAND] - res.summary[CLAIM2]) < 1)


def case_within_limit_regression():
    print("CASE 4 — সীমার মধ্যে: পূর্বের আচরণ অপরিবর্তিত")
    # base 1000 + গৃহীত 300; সম্ভাব্য 1200 → সীমা 400 → ceiling = 1300
    res = _run(taken=300, probable=1200, ref_date=date(2026, 6, 30), imported=1200)
    rec = res.provisional_records[0]
    check("status = সীমার মধ্যে", rec.status == "সীমার মধ্যে")
    check("excess = 0", abs(rec.excess_quantity) < 1e-9)
    check("দাবিনামা প্রস্তাব খালি", rec.demand_proposal == "")
    check("আমদানি 1200 < ceiling 1300 → কোনো excess record নাই",
          len(res.excess_records) == 0)
    check("দাবি ২ = 0", res.summary[CLAIM2] == 0)


def case_no_probable_given():
    print("CASE 5 — সম্ভাব্য প্রাপ্যতা না দিলে: যাচাই নাই, কিন্তু সতর্কবার্তা")
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00",
                          item_name="COTTON YARN", entitled_quantity=1000.0,
                          extended_entitlement=900.0, unit="KG", **_period())]
    imp = [ImportRow(row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
                     hs_code="5205.11.00", item_name="COTTON YARN",
                     quantity=1500, unit="KG", value_bdt=1_000_000)]
    res = ImportAnalysisEngine(ent, imp).analyze()
    check("কোনো provisional record নাই", len(res.provisional_records) == 0)
    check("সম্ভাব্য প্রাপ্যতা তলবের সতর্কবার্তা",
          any("সম্ভাব্য প্রাপ্যতা" in w for w in res.warnings))
    check("ceiling পূর্ববৎ = 1900 (সীমা প্রযোজ্য নহে)",
          bool(res.excess_records) is False or
          abs(res.excess_records[0].entitled_quantity - 1900) < 0.01)


def case_date_fallback():
    print("CASE 6 — তারিখ না দিলে fallback + সতর্কবার্তা")
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00",
                          item_name="COTTON YARN", entitled_quantity=1000.0,
                          extended_entitlement=900.0, next_period_probable=1200.0,
                          unit="KG", **_period())]
    imp = [ImportRow(row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
                     hs_code="5205.11.00", item_name="COTTON YARN",
                     quantity=1500, unit="KG", value_bdt=1_000_000)]
    res = ImportAnalysisEngine(ent, imp).analyze()
    check("record তৈরি হয়", len(res.provisional_records) == 1)
    check("তারিখ-যাচাইয়ের সতর্কবার্তা",
          any("তারিখ" in w and "বিয়োজনের শর্তে" in w for w in res.warnings))


for fn in (case_old_regime_divisor, case_new_regime_divisor,
           case_excess_no_longer_shields, case_within_limit_regression,
           case_no_probable_given, case_date_fallback):
    fn()
    print()

print("RESULT:", "ALL PASS ✅" if _all_ok else "❌ FAILURES")
sys.exit(0 if _all_ok else 1)
