"""
Correction — অতিরিক্ত আমদানি (দাবি ২) প্রবেশক্রম register-ভিত্তিক, FIFO নয়।

চালান:  python3 tests/test_register_driven_excess.py

নিরীক্ষক নিয়ম: কাঁচামালের প্রবেশ = বন্ড রেজিস্টার (তফসিল-১) এর ইন্টু-বন্ড তারিখ;
ব্যবহার = এক্স-বন্ড তারিখ। FIFO (বিল অব এন্ট্রির তারিখ) অনুমান বাদ।

যাচাই করে: BE-তারিখ ও ইন্টু-বন্ড তারিখ ভিন্ন হইলে অতিরিক্ত বিল ও দাবি বদলায়।
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import date
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow
from services.capacity_ledger import LedgerEvent
from services.bond_register import RegisterDecision

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def _run(with_register: bool):
    ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00", item_name="COTTON",
                          entitled_quantity=1000.0, unit="KG",
                          period_from=date(2025, 1, 1), period_to=date(2025, 12, 31))]
    # A: BE জানুয়ারি, ইন্টু-বন্ড সেপ্টেম্বর, উচ্চ শুল্ক; B: BE জুন, ইন্টু-বন্ড ফেব্রুয়ারি, নিম্ন শুল্ক
    a = ImportRow(row_id=1, bill_number="A", bill_date=date(2025, 1, 1), hs_code="5205.11.00",
                  item_name="COTTON", quantity=600, unit="KG", qty_kg=600,
                  value_bdt=600000, duty_paid=60000)
    b = ImportRow(row_id=2, bill_number="B", bill_date=date(2025, 6, 1), hs_code="5205.11.00",
                  item_name="COTTON", quantity=600, unit="KG", qty_kg=600,
                  value_bdt=600000, duty_paid=6000)
    ev = rd = None
    if with_register:
        ev = [
            LedgerEvent(event_date=date(2025, 9, 1), kind="into_bond", reference="A",
                        qty_kg=600, hs_code="5205.11.00", item_name="COTTON"),
            LedgerEvent(event_date=date(2025, 2, 1), kind="into_bond", reference="B",
                        qty_kg=600, hs_code="5205.11.00", item_name="COTTON"),
        ]
        rd = RegisterDecision(provided=True, file_path="x")
    return ImportAnalysisEngine(ent, [a, b], ledger_events=ev, register_decision=rd,
                                warehouse_capacity_mt=2.0).analyze()


if __name__ == "__main__":
    print("NO register — প্রবেশক্রম BE-তারিখে (আনুমানিক)")
    r0 = _run(False)
    ex0 = r0.excess_records[0]
    print(f"  excess bill: {ex0.excess_bills} | দাবি: {ex0.total_revenue_impact}")
    check("অতিরিক্ত বিল = B (BE জুন শেষ)", "B" in ex0.excess_bills and "A (" not in ex0.excess_bills)
    check("রেজিস্টার-অনুপস্থিতির আনুমানিক সতর্কতা", any("আনুমানিক" in w for w in r0.warnings))

    print("WITH register — প্রবেশক্রম ইন্টু-বন্ড তারিখে")
    r1 = _run(True)
    ex1 = r1.excess_records[0]
    print(f"  excess bill: {ex1.excess_bills} | দাবি: {ex1.total_revenue_impact}")
    check("অতিরিক্ত বিল = A (ইন্টু-বন্ড সেপ্টেম্বর শেষ)", "A (" in ex1.excess_bills)
    check("register দাবি (20000) > FIFO দাবি (2000)", ex1.total_revenue_impact > ex0.total_revenue_impact * 3)
    check("ইন্টু-বন্ড তারিখ প্রয়োগের সতর্কতা", any("ইন্টু-বন্ড তারিখ প্রয়োগ" in w for w in r1.warnings))
    check("রেজিস্টার দিলে ক্যাপাসিটি যাচাই স্থগিত নয়", r1.bonding_value.status != "যাচাই স্থগিত")

    print()
    print("RESULT:", "ALL PASS ✅" if _all_ok else "SOME FAILED ❌")
    sys.exit(0 if _all_ok else 1)
