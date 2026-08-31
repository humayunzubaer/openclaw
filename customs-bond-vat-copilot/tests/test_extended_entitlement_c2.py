"""
C2 — বর্ধিত প্রাপ্যতা [বিধি ৮] + বিয়োজন যাচাই regression test.

চালান:  python3 tests/test_extended_entitlement_c2.py

যাচাই করে:
  • extended_entitlement দিলে সীমা = মূল + বর্ধিত (combined); excess ঐ combined-এর বিপরীতে
  • বিধি ৮ পর্যবেক্ষণ (overall + item) তৈরি হয়; দাবি নহে (রাজস্ব যোগ হয় না)
  • extension_applies flag দিলে (per-item ছাড়া) — শুধু overall পর্যবেক্ষণ
  • কিছু না দিলে — কোনো পর্যবেক্ষণ নাই, effective==base (regression)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow

R8_KEY = "বিধি ৮ বর্ধিত-প্রাপ্যতা পর্যবেক্ষণ (দাবি নহে)"
_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def _period():
    return dict(period_from=date(2025, 1, 1), period_to=date(2025, 12, 31))


def case_extended():
    # Case-B pattern: base 894.269 + extended 516.816 = 1411.085; import 1552.376
    print("CASE 1 — extended entitlement (combined ceiling, Case-B)")
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="3915.90.00",
                          item_name="MIXED PLASTIC SCRAP", entitled_quantity=894.269,
                          extended_entitlement=516.816, unit="MT", **_period())]
    imp = [ImportRow(row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
                     hs_code="3915.90.00", item_name="MIXED PLASTIC SCRAP",
                     quantity=1552.376, unit="MT", value_usd=100000, value_bdt=11000000,
                     duty_paid=1000000, vat_paid=500000)]
    res = ImportAnalysisEngine(ent, imp).analyze()
    ex = res.excess_records
    check("1 excess record", len(ex) == 1)
    check("ceiling = combined 1411.085", bool(ex) and abs(ex[0].entitled_quantity - 1411.085) < 0.01)
    check("excess = 141.291", bool(ex) and abs(ex[0].excess_quantity - 141.291) < 0.01)
    check("rule8 observations = 2 (overall + item)", len(res.rule8_observations) == 2)
    check("summary rule8 count = 2", res.summary[R8_KEY] == 2)
    check("বিধি ৮ surfaced in warnings", any("বিধি ৮" in w for w in res.warnings))
    it = [o for o in res.rule8_observations if o.scope == "item"]
    check("item obs combined = 1411.085", bool(it) and abs(it[0].combined_entitlement - 1411.085) < 0.01)
    # observation adds no revenue: grand total == claim-2 only
    check("no extra revenue from বিধি ৮ (grand == claim 2)",
          abs(res.summary["সর্বমোট রাজস্ব দাবি (BDT)"]
              - res.summary["দাবি ২ — প্রাপ্যতার অতিরিক্ত আমদানি (BDT)"]) < 1)


def case_flag_only():
    print("CASE 2 — extension_applies flag only (no per-item extended)")
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON",
                          entitled_quantity=1000.0, unit="KG", **_period())]
    imp = [ImportRow(row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
                     hs_code="5205.11.00", item_name="COTTON", quantity=800, unit="KG",
                     value_bdt=800000)]
    res = ImportAnalysisEngine(ent, imp, extension_applies=True).analyze()
    obs = res.rule8_observations
    check("only overall observation (1)", len(obs) == 1 and obs[0].scope == "overall")


def case_none():
    print("CASE 3 — regression: no extension, no flag")
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON",
                          entitled_quantity=1000.0, unit="KG", **_period())]
    imp = [ImportRow(row_id=1, bill_number="B1", bill_date=date(2025, 6, 1),
                     hs_code="5205.11.00", item_name="COTTON", quantity=800, unit="KG",
                     value_bdt=800000)]
    res = ImportAnalysisEngine(ent, imp).analyze()
    check("no rule8 observations", len(res.rule8_observations) == 0)
    check("no বিধি ৮ warning", not any("বিধি ৮" in w for w in res.warnings))
    check("util entitled = 1000 (effective == base)", res.utilization_records[0].entitled_quantity == 1000.0)
    check("util extended_quantity = 0", res.utilization_records[0].extended_quantity == 0.0)


if __name__ == "__main__":
    case_extended()
    print()
    case_flag_only()
    print()
    case_none()
    print()
    print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
    sys.exit(0 if _all_ok else 1)
