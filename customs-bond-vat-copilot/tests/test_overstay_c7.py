"""
C7 — মেয়াদোত্তীর্ণ (overstay) কাঁচামাল = দাবি ৬ (register-ভিত্তিক, সর্বমোটে যুক্ত)।

চালান:  python3 tests/test_overstay_c7.py

নিরীক্ষক: overstay পৃথক দাবি হিসেবে সর্বমোটে যোগ হবে। রেজিস্টার (তফসিল-১) এর
প্রতিটি সারির ইন্টু/এক্স-বন্ড linkage হইতে অবশিষ্ট নির্ণয়; ইন্টু-বন্ড তারিখ
কর্তন-সীমার (as-of − ২ বছর) আগে ও অবশিষ্ট > 0 হইলে overstay।
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow
from services.capacity_ledger import LedgerEvent

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def _ent():
    return [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON",
                           entitled_quantity=1000.0, unit="KG",
                           period_from=date(2025, 1, 1), period_to=date(2025, 12, 31))]


def _imports():
    return [
        ImportRow(row_id=1, bill_number="OLD", bill_date=date(2022, 1, 1), hs_code="5205.11.00",
                  item_name="COTTON", quantity=500, unit="KG", qty_kg=500, value_bdt=500000, duty_paid=50000),
        ImportRow(row_id=2, bill_number="NEW", bill_date=date(2025, 6, 1), hs_code="5205.11.00",
                  item_name="COTTON", quantity=400, unit="KG", qty_kg=400, value_bdt=400000, duty_paid=40000),
    ]


def _events():
    return [
        LedgerEvent(event_date=date(2022, 6, 1), kind="into_bond", reference="OLD", qty_kg=500,
                    row_number=1, hs_code="5205.11.00", item_name="COTTON"),
        LedgerEvent(event_date=date(2023, 1, 1), kind="ex_bond", reference="OLD", qty_kg=200, row_number=1),
        LedgerEvent(event_date=date(2025, 6, 1), kind="into_bond", reference="NEW", qty_kg=400,
                    row_number=2, hs_code="5205.11.00", item_name="COTTON"),
    ]


CLAIM6 = "দাবি ৬ — মেয়াদোত্তীর্ণ (২ বছর+) কাঁচামাল (BDT)"
TOTAL = "সর্বমোট রাজস্ব দাবি (BDT)"

res = ImportAnalysisEngine(_ent(), _imports(), ledger_events=_events()).analyze()
ov = res.overstay_records
check("1 overstay record", len(ov) == 1)
check("overstay qty = 300 (500 into − 200 ex)", bool(ov) and abs(ov[0].overstay_quantity_kg - 300) < 0.01)
check("only OLD bill (NEW after cutoff excluded)", bool(ov) and ov[0].bill_numbers == "OLD")
check("tax = 0.6 × 50000 = 30000", bool(ov) and abs(ov[0].total_revenue_impact - 30000) < 1)
check("summary দাবি ৬ = 30000", abs(res.summary[CLAIM6] - 30000) < 1)
check("grand total includes দাবি ৬", res.summary[TOTAL] >= 30000)

res2 = ImportAnalysisEngine(_ent(), _imports()).analyze()
check("no register → 0 overstay + warning",
      len(res2.overstay_records) == 0 and any("মেয়াদোত্তীর্ণ" in w for w in res2.warnings))

# custom threshold: 5 years → OLD (2022) not overstayed relative to as-of 2025-12-31
res3 = ImportAnalysisEngine(_ent(), _imports(), ledger_events=_events(), overstay_years=5.0).analyze()
check("5-year threshold → no overstay (2022 within 5yr of 2025)", len(res3.overstay_records) == 0)

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
sys.exit(0 if _all_ok else 1)
