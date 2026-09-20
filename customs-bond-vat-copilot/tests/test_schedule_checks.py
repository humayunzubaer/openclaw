"""
তফসিল-ভিত্তিক তিনটি যাচাই — regression test.

চালান:  python3 tests/test_schedule_checks.py

  ১. বিধি ৮ — ছাড়করণ → ইন্টু-বন্ড বিলম্ব (৫ দিন, কমিশনার +৭)
  ২. বিধি ৯ — সহগের মেয়াদ ও সমজাতীয় সহগের ৩০-দিন সীমা
  ৩. ইউপির গাণিতিক যোগফল
  ৪. engine-এ বিধি ৮ স্বয়ংক্রিয় (রেজিস্টার দিলেই)
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.schedule_checks import (
    check_into_bond_delay, check_coefficient_validity, check_up_arithmetic,
    INTO_BOND_BASE_DAYS, INTO_BOND_MAX_EXTENSION, SIMILAR_COEFFICIENT_MAX_DAYS,
)
from services.capacity_ledger import LedgerEvent
from services.import_analysis import ImportAnalysisEngine, EntitlementRow, ImportRow

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def ev(rel, into, qty=1000.0, ref="B-1", row=1):
    return LedgerEvent(
        event_date=into, kind="into_bond", hs_code="5205.11.00",
        item_name="COTTON YARN", qty_kg=qty, reference=ref, row_number=row,
        release_date=rel,
    )


print("== আইনি ধ্রুবক 【V】 ==")
check("বিধি ৮ ভিত্তি = ৫ দিন", INTO_BOND_BASE_DAYS == 5)
check("বিধি ৮ কমিশনার সর্বোচ্চ = ৭ দিন", INTO_BOND_MAX_EXTENSION == 7)
check("বিধি ৯ সমজাতীয় সহগ = ৩০ দিন", SIMILAR_COEFFICIENT_MAX_DAYS == 30)

print("== ১. বিধি ৮ — ইন্টু-বন্ড বিলম্ব ==")
recs = check_into_bond_delay([
    ev(date(2025, 3, 1), date(2025, 3, 4), ref="B-A", row=1),   # ৩ দিন — ঠিক
    ev(date(2025, 3, 1), date(2025, 3, 6), ref="B-B", row=2),   # ৫ দিন — সীমায়
    ev(date(2025, 3, 1), date(2025, 3, 9), ref="B-C", row=3),   # ৮ দিন — ৩ দিন বিলম্ব
])
check("৩টি রেকর্ড", len(recs) == 3)
check("৩ দিন → সীমার মধ্যে", recs[0].status == "সীমার মধ্যে")
check("ঠিক ৫ দিন → সীমার মধ্যে (সীমান্ত)", recs[1].status == "সীমার মধ্যে")
check("৮ দিন → সীমা অতিক্রম", recs[2].status == "সীমা অতিক্রম")
check("বিলম্ব = ৩ দিন", recs[2].excess_days == 3)
check("অনুমোদিত = ৫ দিন", recs[2].allowed_days == 5)
check("আইনি ভিত্তিতে বিধি ৮", "বিধি ৮" in recs[2].legal_basis)

print("== কমিশনার-বর্ধিত সময় ==")
r_ext = check_into_bond_delay([ev(date(2025, 3, 1), date(2025, 3, 9))],
                              commissioner_extension_days=7)
check("+৭ দিন দিলে ৮ দিন সীমার মধ্যে", r_ext[0].status == "সীমার মধ্যে")
check("অনুমোদিত = ১২ দিন", r_ext[0].allowed_days == 12)
r_cap = check_into_bond_delay([ev(date(2025, 3, 1), date(2025, 3, 20))],
                              commissioner_extension_days=30)
check("৭ দিনের বেশি চাইলে ৭-এ সীমাবদ্ধ", r_cap[0].allowed_days == 12)
check("১৯ দিন → তবু সীমা অতিক্রম", r_cap[0].status == "সীমা অতিক্রম")

print("== প্রান্তিক অবস্থা ==")
r_none = check_into_bond_delay([ev(None, date(2025, 3, 4))])
check("ছাড়করণ তারিখ নাই → তথ্য অসম্পূর্ণ", r_none[0].status == "তথ্য অসম্পূর্ণ")
r_rev = check_into_bond_delay([ev(date(2025, 3, 10), date(2025, 3, 4))])
check("ইন্টু-বন্ড ছাড়করণের আগে → ক্রম-বিপর্যয়", r_rev[0].status == "ক্রম-বিপর্যয়")
r_ex = check_into_bond_delay([
    LedgerEvent(event_date=date(2025, 3, 4), kind="ex_bond", qty_kg=100.0)
])
check("এক্স-বন্ড ঘটনা উপেক্ষিত", len(r_ex) == 0)

print("== ২. বিধি ৯ — সহগের মেয়াদ ==")
cv = check_coefficient_validity([
    {"up_no": "UP-01", "issue_date": "2025-03-01", "coefficient_ref": "DEDO/1",
     "valid_from": "2024-01-01", "valid_to": "2025-12-31"},
    {"up_no": "UP-02", "issue_date": "2025-03-01", "coefficient_ref": "DEDO/2",
     "valid_from": "2022-01-01", "valid_to": "2022-07-20"},
    {"up_no": "UP-03", "issue_date": "2025-03-01", "coefficient_ref": "DEDO/3"},
])
check("UP-01 বৈধ", cv[0].status == "বৈধ")
check("UP-02 মেয়াদোত্তীর্ণ", cv[1].status == "মেয়াদোত্তীর্ণ")
check("মেয়াদোত্তীর্ণ দিন গণনা > 0", cv[1].days_expired > 0)
check("UP-03 মেয়াদ না দিলে তথ্য অসম্পূর্ণ (অনুমান নয়)",
      cv[2].status == "তথ্য অসম্পূর্ণ")
check("অনুমিত মেয়াদ বসানো হয় নাই", cv[2].valid_to == "")

print("== সমজাতীয় সহগের ৩০-দিন সীমা ==")
sim = check_coefficient_validity([
    {"up_no": "UP-04", "issue_date": "2025-02-01", "similar_coefficient": True,
     "similar_since": "2025-01-20"},                       # ১২ দিন — ঠিক
    {"up_no": "UP-05", "issue_date": "2025-03-15", "similar_coefficient": True,
     "similar_since": "2025-01-20"},                       # ৫৪ দিন — লঙ্ঘন
])
check("১২ দিন → বৈধ", sim[0].status == "বৈধ")
check("৫৪ দিন → সমজাতীয়-সীমা অতিক্রম", sim[1].status == "সমজাতীয়-সীমা অতিক্রম")
check("অতিক্রান্ত = ২৪ দিন", sim[1].days_expired == 24)

print("== ৩. ইউপির গাণিতিক যোগফল ==")
ar = check_up_arithmetic([
    {"up_no": "UP-01", "declared_total": 65.233, "unit": "MT",
     "line_items": [30.0, 25.0, 10.233]},                  # মিল
    {"up_no": "UP-02", "declared_total": 65.233, "unit": "MT",
     "line_items": [30.0, 25.0, 19.668]},                  # ঘোষিত কম
    {"up_no": "UP-03", "declared_total": 80.0, "unit": "MT",
     "line_items": [30.0, 25.0, 10.0]},                    # ঘোষিত অধিক
    {"up_no": "UP-04", "declared_total": 0, "line_items": []},
])
check("UP-01 মিল আছে", ar[0].status == "মিল আছে")
check("যোগফল = 65.233", abs(ar[0].computed_total - 65.233) < 1e-6)
check("UP-02 ঘোষিত কম", ar[1].status == "ঘোষিত কম")
check("UP-03 ঘোষিত অধিক", ar[2].status == "ঘোষিত অধিক")
check("পার্থক্য = 15.0", abs(ar[2].difference - 15.0) < 1e-6)
check("লাইন সংখ্যা = 3", ar[2].line_count == 3)
check("UP-04 তথ্য অসম্পূর্ণ", ar[3].status == "তথ্য অসম্পূর্ণ")
tol = check_up_arithmetic(
    [{"up_no": "X", "declared_total": 100.05, "line_items": [100.0]}],
    tolerance=0.1)
check("সহনসীমা দিলে সামান্য পার্থক্য মিল ধরে", tol[0].status == "মিল আছে")

print("== ৪. engine-এ বিধি ৮ স্বয়ংক্রিয় ==")
ent = [EntitlementRow(row_id=1, serial_no="1", hs_code="5205.11.00",
                      item_name="COTTON YARN", entitled_quantity=100000.0,
                      unit="KG", period_from=date(2025, 1, 1),
                      period_to=date(2025, 12, 31))]
imp = [ImportRow(row_id=1, bill_number="B-C", bill_date=date(2025, 3, 1),
                 hs_code="5205.11.00", item_name="COTTON YARN",
                 quantity=1000, unit="KG", value_bdt=500000)]
events = [
    ev(date(2025, 3, 1), date(2025, 3, 4), ref="B-A", row=1),
    ev(date(2025, 3, 1), date(2025, 3, 9), ref="B-C", row=2),
]
res = ImportAnalysisEngine(ent, imp, ledger_events=events).analyze()
check("engine-এ রেকর্ড এসেছে", len(res.into_bond_delay_records) == 2)
check("১টি সীমা অতিক্রম",
      sum(1 for r in res.into_bond_delay_records
          if r.status == "সীমা অতিক্রম") == 1)
check("summary-তে গণনা",
      res.summary["ইন্টু-বন্ড বিলম্ব [বিধি ৮] — সীমা অতিক্রম"] == 1)
check("সতর্কবার্তা এসেছে", any("বিধি ৮" in w for w in res.warnings))
check("দাবিতে যোগ হয় নাই (পর্যবেক্ষণ)",
      res.summary["সর্বমোট রাজস্ব দাবি (BDT)"] == 0)

res_ext = ImportAnalysisEngine(ent, imp, ledger_events=events,
                               commissioner_extension_days=7).analyze()
check("কমিশনার-বর্ধিত দিলে লঙ্ঘন শূন্য",
      res_ext.summary["ইন্টু-বন্ড বিলম্ব [বিধি ৮] — সীমা অতিক্রম"] == 0)

res_noreg = ImportAnalysisEngine(ent, imp).analyze()
check("রেজিস্টার না দিলে যাচাই নাই", len(res_noreg.into_bond_delay_records) == 0)

print("== ৫. বন্ড রেজিস্টার ফাইল হইতে (তফসিল-১ বাংলা হেডার) ==")
import tempfile
from pathlib import Path as _P
from openpyxl import Workbook
from services.capacity_ledger import BondRegisterReader

_headers = [
    "বিল অব এন্ট্রি নম্বর ও তারিখ",
    "আমদানি কাস্টম হাউস/স্টেশনের নাম",
    "পণ্যচালান কাস্টম হাউস/স্টেশন হইতে ছাড়করণের তারিখ\n(এক্সিট নোটের তারিখ)",
    "এলসি নং ও তারিখ", "এইচএস কোড", "পণ্যের বাণিজ্যিক বর্ণনা",
    "কাঁচামালের পরিমাণ (কেজি)", "ইন্টু বন্ডের তারিখ",
    "এক্স বন্ডের তারিখ", "এক্সবন্ডকৃত পণ্যের পরিমাণ",
]
_wb = Workbook(); _ws = _wb.active
_ws.append(_headers)
_ws.append(["C-102345", "চট্টগ্রাম", date(2025, 3, 1), "LC-9", "5205.11.00",
            "COTTON YARN", 5000, date(2025, 3, 4), date(2025, 5, 1), 2000])
_ws.append(["C-102876", "চট্টগ্রাম", date(2025, 3, 1), "LC-9", "5205.11.00",
            "COTTON YARN", 3000, date(2025, 3, 12), None, None])
with tempfile.TemporaryDirectory() as _td:
    _f = _P(_td) / "reg.xlsx"; _wb.save(_f)
    _evs = BondRegisterReader(verbose=False).read(_f)

_into = [e for e in _evs if e.kind == "into_bond"]
_ex = [e for e in _evs if e.kind == "ex_bond"]
check("বাংলা হেডার হইতে ২টি ইন্টু-বন্ড পড়া গিয়াছে", len(_into) == 2)
check("১টি এক্স-বন্ড পড়া গিয়াছে", len(_ex) == 1)
check("পরিমাণ (কেজি) শনাক্ত", bool(_into) and _into[0].qty_kg == 5000.0)
check("কলাম ৩ (ছাড়করণ/এক্সিট নোট) শনাক্ত",
      bool(_into) and all(e.release_date is not None for e in _into))
check("বিল অব এন্ট্রি নম্বর উদ্ধার (তারিখ-রূপান্তরে হারায় নাই)",
      bool(_into) and all("C-10" in (e.reference or "") for e in _into))
_frecs = check_into_bond_delay(_into)
check("ফাইল হইতে বিলম্ব-যাচাই: ১টি সীমা অতিক্রম",
      sum(1 for r in _frecs if r.status == "সীমা অতিক্রম") == 1)

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "❌ FAILURES")
sys.exit(0 if _all_ok else 1)
