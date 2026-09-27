"""
C1 — মেয়াদোত্তর আমদানি (post-period import as দাবি ৫) regression test.

চালান:  python3 tests/test_post_period_c1.py
(pandas, numpy, openpyxl প্রয়োজন)

যাচাই করে:
  • period_to-এর পরের আমদানি ও স্থানীয় ক্রয় → দাবি ৫ (পূর্ণ BE / ১৫% উৎসে মূসক)
  • মেয়াদোত্তর unmatched HS বিল দাবি ৫-এ যায়, অননুমোদিত (দাবি ১)-এ নয় — দ্বৈত দাবি রোধ
  • প্রাক-মেয়াদ (period_from-এর আগে) বিল দাবি ৫-এ ধরা হয় না
  • next_entitlement_date দিলে তার পরের বিল বাদ; না দিলে সব ধরা হয় + সতর্কতা
  • সর্বমোট দাবিতে দাবি ৫ যুক্ত হয়
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow

CLAIM5 = "দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি (BDT)"
TOTAL = "সর্বমোট রাজস্ব দাবি (BDT)"

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def _ent():
    return [EntitlementRow(
        row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON YARN",
        entitled_quantity=1000.0, unit="KG",
        period_from=date(2025, 1, 1), period_to=date(2025, 12, 31),
    )]


def _imports():
    return [
        ImportRow(row_id=1, bill_number="B-IN", bill_date=date(2025, 6, 1),
                  hs_code="5205.11.00", item_name="COTTON YARN", quantity=800, unit="KG",
                  value_usd=8000, value_bdt=880000),
        ImportRow(row_id=2, bill_number="B-PRE", bill_date=date(2024, 12, 1),
                  hs_code="5205.11.00", item_name="COTTON YARN", quantity=50, unit="KG",
                  value_usd=500, value_bdt=55000, duty_paid=1000, vat_paid=500),
        ImportRow(row_id=3, bill_number="B-POST1", bill_date=date(2026, 2, 1),
                  hs_code="5205.11.00", item_name="COTTON YARN", quantity=300, unit="KG",
                  value_usd=3000, value_bdt=330000,
                  duty_paid=10000, vat_paid=5000, at_paid=2000, ait_paid=2000),
        ImportRow(row_id=4, bill_number="B-POST-UNAUTH", bill_date=date(2026, 2, 15),
                  hs_code="9999.99.99", item_name="RANDOM CHEMICAL", quantity=20, unit="KG",
                  value_usd=2000, value_bdt=220000,
                  duty_paid=8000, vat_paid=3000, at_paid=1000, ait_paid=1000),
        ImportRow(row_id=5, bill_number="B-AFTER-NEW", bill_date=date(2026, 5, 1),
                  hs_code="5205.11.00", item_name="COTTON YARN", quantity=100, unit="KG",
                  value_usd=1000, value_bdt=110000, duty_paid=4000, vat_paid=2000),
    ]


def _local():
    return [ImportRow(row_id=101, bill_number="L-POST", bill_date=date(2026, 3, 1),
                      hs_code="5205.11.00", item_name="COTTON YARN", quantity=40, unit="KG",
                      value_bdt=100000, source_type="local_purchase")]


def _bills(records):
    out = set()
    for r in records:
        out |= {x.strip() for x in r.bill_numbers.split(",")}
    return out


def case_a():
    print("CASE A — next_entitlement_date = 2026-04-01")
    res = ImportAnalysisEngine(_ent(), _imports(), local_purchases=_local(),
                               next_entitlement_date=date(2026, 4, 1)).analyze()
    pp = _bills(res.post_period_records)
    un = _bills(res.unauthorized_records)
    ex = set()
    for r in res.excess_records:
        ex |= {x.strip() for x in r.bill_numbers.split(",")}

    check("B-POST1 in দাবি ৫", "B-POST1" in pp)
    check("B-POST-UNAUTH in দাবি ৫", "B-POST-UNAUTH" in pp)
    check("B-POST-UNAUTH NOT in unauthorized (no double count)", "B-POST-UNAUTH" not in un)
    check("দাবি ৫ ∩ অননুমোদিত = ∅", not (pp & un))
    check("দাবি ৫ ∩ অতিরিক্ত = ∅", not (pp & ex))
    check("B-PRE (pre-period) excluded", "B-PRE" not in pp)
    check("B-AFTER-NEW (>= next date) excluded", "B-AFTER-NEW" not in pp)
    check("L-POST local purchase in দাবি ৫", "L-POST" in pp)

    lp = [r for r in res.post_period_records if r.source == "স্থানীয় ক্রয়"]
    check("local 15% উৎসে মূসক = 15000",
          bool(lp) and abs(lp[0].total_revenue_impact - 15000) < 1)
    p1 = [r for r in res.post_period_records if "B-POST1" in r.bill_numbers]
    check("B-POST1 পূর্ণ BE = 19000", bool(p1) and abs(p1[0].total_revenue_impact - 19000) < 1)
    check("সর্বমোট = 47000 (19000+13000+15000)", abs(res.summary[TOTAL] - 47000) < 1)


def case_b():
    print("CASE B — next_entitlement_date = None (include all after period_to + warn)")
    res = ImportAnalysisEngine(_ent(), _imports(), local_purchases=_local(),
                               next_entitlement_date=None).analyze()
    pp = _bills(res.post_period_records)
    warned = any("নূতন প্রাপ্যতা" in w and "তারিখ" in w for w in res.warnings)
    check("B-AFTER-NEW included when no next date", "B-AFTER-NEW" in pp)
    check("warning emitted about missing next-entitlement date", warned)
    check("সর্বমোট = 53000 (+6000)", abs(res.summary[TOTAL] - 53000) < 1)


def case_regression():
    print("CASE C — regression: in-period দাবি ১ ও দাবি ২ অক্ষত")
    ent = _ent()
    imp = [
        ImportRow(row_id=1, bill_number="X1", bill_date=date(2025, 3, 1), hs_code="5205.11.00",
                  item_name="COTTON YARN", quantity=700, unit="KG", value_usd=7000,
                  value_bdt=770000, duty_paid=7000, vat_paid=3000),
        ImportRow(row_id=2, bill_number="X2", bill_date=date(2025, 9, 1), hs_code="5205.11.00",
                  item_name="COTTON YARN", quantity=600, unit="KG", value_usd=6000,
                  value_bdt=660000, duty_paid=6000, vat_paid=3000, at_paid=1000, ait_paid=1000),
        ImportRow(row_id=3, bill_number="U1", bill_date=date(2025, 5, 1), hs_code="8888.00.00",
                  item_name="MYSTERY DYE", quantity=50, unit="KG", value_usd=5000,
                  value_bdt=550000, duty_paid=20000, vat_paid=8000, at_paid=2000, ait_paid=2000),
    ]
    res = ImportAnalysisEngine(ent, imp).analyze()
    check("excess=1, unauthorized=1, post-period=0",
          len(res.excess_records) == 1 and len(res.unauthorized_records) == 1
          and len(res.post_period_records) == 0)
    check("দাবি ৫ = 0 when no post-period bills", res.summary[CLAIM5] == 0)


if __name__ == "__main__":
    case_a()
    print()
    case_b()
    print()
    case_regression()
    print()
    print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
    sys.exit(0 if _all_ok else 1)
