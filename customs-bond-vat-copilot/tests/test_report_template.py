"""
প্রতিবেদন-টেমপ্লেট ও গোপনীয়তা — regression test.

চালান:  python3 tests/test_report_template.py

  ১. প্রস্তাবনা-ছাঁচ: সব kind রেন্ডার হয়, KeyError নাই
  ২. টাকার অঙ্ক + কথায় দুই-ই থাকে
  ৩. ভাষা-নীতি: "করা যেতে পারে" থাকে, আদেশসূচক নাই
  ৪. KB মডিউল ২৮ (লিখন-টেমপ্লেট) লোড হয়
  ৫. ★ PII প্রহরী — নিরীক্ষাধীন প্রতিষ্ঠানের নাম কোথাও নাই
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from knowledge.report_style import (
    OPINION_TEMPLATES, OPINION_OPENING, OPINION_CLOSING,
    REVIEW_CHECKLIST, REPORT_SKELETON, build_opinion,
    number_to_bangla_words,
    AuditProfile, assemble_report_plan, template_applies,
    select_report_paragraphs, select_review_questions,
)

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


print("== ১. প্রস্তাবনা-ছাঁচের ভাণ্ডার ==")
check("≥ ১৮টি ছাঁচ", len(OPINION_TEMPLATES) >= 18)
for k in ("overstay_demand", "provisional_excess_demand", "coefficient_expired",
          "into_bond_delay", "up_arithmetic", "export_without_up",
          "value_addition_short", "electricity_inconsistency"):
    check(f"নতুন ছাঁচ আছে: {k}", k in OPINION_TEMPLATES)

print("== ২. রেন্ডারিং — KeyError ছাড়া ==")
findings = [
    {"kind": "excess_import_demand", "para": "৩৬", "quantity": "১৪১.২৯১",
     "unit": "মেঃ টন", "amount": 1542936.0},
    {"kind": "provisional_excess_demand", "para": "৩৭", "taken": "২৫,০০০",
     "cap": "২০,০০০", "excess": "৫,০০০", "unit": "কেজি", "amount": 875400.0},
    {"kind": "overstay_demand", "para": "৩৮", "quantity": "৩,২০০",
     "unit": "কেজি", "amount": 412500.0},
    {"kind": "coefficient_expired", "para": "২৫", "expiry_date": "২০-০৭-২০২২",
     "up_count": "২", "amount": 0},
    {"kind": "into_bond_delay", "para": "১৯", "count": "৭", "amount": 0},
    {"kind": "up_arithmetic", "para": "১৭", "up_no": "UP-01",
     "declared": "৬৫.২৩৩", "computed": "৫০.২৩৩", "difference": "১৫.০০০",
     "unit": "মেঃ টন", "amount": 0},
    {"kind": "export_without_up", "para": "২২", "quantity": "৩০,২৫০",
     "unit": "পিস", "value_usd": "৫৬,৩২৫.৫০", "pct": "৩২.৬৬", "amount": 0},
    {"kind": "value_addition_short", "para": "২৬", "rate": "১১.৪০", "amount": 0},
    {"kind": "electricity_inconsistency", "para": "৩০", "declared_rate": "৪.০০",
     "actual_rate": "৫.২০", "deviation": "+৩০.০", "amount": 0},
]
items = build_opinion("নমুনা লিমিটেড", "০১-০১-২০২৫", "৩১-১২-২০২৫",
                      findings=findings, entitlement_para="৪০")
check("সব দফা তৈরি (২ + ৯ = ১১)", len(items) == 11)
check("কোনো ছাঁচ-পূরণ ব্যর্থতা নাই",
      not any("ছাঁচ পূরণ করা যায় নাই" in i.text for i in items))
check("প্রতিটি দফায় লেবেল আছে", all(i.label for i in items))

print("== ৩. ভাষা-নীতি ==")
demand_items = [i for i in items if i.amount > 0]
check("দাবির দফা ৩টি", len(demand_items) == 3)
for i in demand_items:
    check(f"[{i.kind}] অঙ্ক ও কথায় দুই-ই আছে",
          "টাকা" in i.text and "(" in i.text and ")" in i.text)
check("সব দফায় 'করা যেতে পারে'",
      all("করা যেতে পারে" in i.text or "দেওয়া যেতে পারে" in i.text
          for i in items))
check("আদেশসূচক 'করতে হবে' নাই",
      not any("করতে হবে" in i.text for i in items))
check("সাধু ক্রিয়া 'হইয়াছে' নাই", not any("হইয়াছে" in i.text for i in items))
check("সমাপনী বাক্য সঠিক", OPINION_CLOSING.startswith("সদয় অনুমোদনের"))
check("সূচনা বাক্যে অনুচ্ছেদ-সূত্র", "{from_para}" in OPINION_OPENING)

print("== ৪. কাঠামো ও পর্যালোচনা ==")
check("প্রতিবেদন-কাঠামো ২ খণ্ড", len(REPORT_SKELETON) == 2)
check("পর্যালোচনা প্রশ্ন ≥ ১০টি", len(REVIEW_CHECKLIST) >= 10)
check("সংখ্যা→কথায় কাজ করে",
      "লক্ষ" in number_to_bangla_words(1542936.0))

print("== ৫. KB মডিউল ২৮ — লিখন টেমপ্লেট ==")
tpl = ROOT / "backend/knowledge/kb/28_KB_REPORT_WRITING_TEMPLATE.md"
check("ফাইল আছে", tpl.exists())
txt = tpl.read_text(encoding="utf-8") if tpl.exists() else ""
for sec in ("ভাষা-নীতি", "প্রেরণপত্র", "অনুচ্ছেদ-মানচিত্র",
            "সার্বিক পর্যালোচনা", "মতামত ও প্রস্তাবনা", "সাধারণ ভুল"):
    check(f"অনুচ্ছেদ আছে: {sec}", sec in txt)
check("প্রস্তাবনার ক্রিয়া-নিয়ম উল্লিখিত", "করা যেতে পারে" in txt)
check("AT/AIT যোগের নির্দেশ আছে", "AIT" in txt and "AT" in txt)

print("== ৬. ★ PII প্রহরী — প্রতিষ্ঠানের নাম কোথাও নাই ==")
BANNED = ["Gold Shine", "গোল্ড শাইন", "Haigenity", "হাইজেন", "RahimAfrooz",
          "রহিমআফরোজ", "Globatt", "গ্লোব্যাট", "Fujian", "ফুজিয়ান",
          "Traveling Goods", "RGL", "Cus-ESB-W", "ঈশ্বরদী ইপিজেড, পাবনা"]
hits = []
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix not in {".py", ".md", ".json"}:
        continue
    if "node_modules" in p.parts or p.name == "test_report_template.py":
        continue
    try:
        s = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for b in BANNED:
        if b in s:
            hits.append(f"{p.relative_to(ROOT)}: {b}")
check("নিরীক্ষাধীন প্রতিষ্ঠানের নাম নাই" + (f" — পাওয়া গেছে: {hits[:3]}" if hits else ""),
      not hits)

print("== ৭. ★ প্রাসঙ্গিকতা-ফিল্টার — কেবল প্রযোজ্য অংশ ==")
ALL_F = [
    {"kind": "excess_import_demand", "para": "৩৬"},
    {"kind": "overstay_demand", "para": "৩৮"},
    {"kind": "into_bond_delay", "para": "১৯"},
    {"kind": "up_arithmetic", "para": "১৭"},
    {"kind": "export_without_up", "para": "২২"},
    {"kind": "destination_mismatch", "para": "২৩"},
    {"kind": "deemed_export_doc_incomplete", "para": "২৪"},
    {"kind": "vds_not_deducted", "para": "২০"},
    {"kind": "turnover_mismatch_fs", "para": "৩৫"},
    {"kind": "value_addition_short", "para": "২৬"},
]

# ধরন ১ — সরাসরি, শুধু বন্ড, রপ্তানি ডেটা নাই
p1 = AuditProfile(has_register=True)
pl1 = assemble_report_plan(p1, ALL_F)
k1 = {f["kind"] for f in pl1["findings"]}
check("ভ্যাট পার্শ্ব না থাকিলে ভ্যাট-ফাইন্ডিং বাদ",
      "vds_not_deducted" not in k1 and "turnover_mismatch_fs" not in k1)
check("রপ্তানি ডেটা না থাকিলে রপ্তানি-ফাইন্ডিং বাদ",
      "export_without_up" not in k1 and "destination_mismatch" not in k1)
check("প্রচ্ছন্নের ফাইন্ডিং সরাসরিতে বাদ",
      "deemed_export_doc_incomplete" not in k1)
check("রেজিস্টার-ভিত্তিক ফাইন্ডিং থাকে",
      "into_bond_delay" in k1 and "overstay_demand" in k1)
check("ভ্যাট-প্রশ্ন পর্যালোচনায় নাই",
      not any(c == "vat" for _, _, c in pl1["review_questions"]))
check("বাদ পড়াগুলির কারণ লিপিবদ্ধ",
      all("কারণ" in d for d in pl1["excluded_findings"]))

# ধরন ২ — সরাসরি + রপ্তানি + সিএ/ভ্যাট
p2 = AuditProfile(has_register=True, has_export_data=True, includes_vat=True)
pl2 = assemble_report_plan(p2, ALL_F)
k2 = {f["kind"] for f in pl2["findings"]}
check("পূর্ণ পরিধিতে ভ্যাট-ফাইন্ডিং আসে", "vds_not_deducted" in k2)
check("পূর্ণ পরিধিতে রপ্তানি-ফাইন্ডিং আসে", "export_without_up" in k2)
check("পূর্ণ পরিধিতেও প্রচ্ছন্নের ফাইন্ডিং বাদ",
      "deemed_export_doc_incomplete" not in k2)
check("পূর্ণ পরিধিতে অনুচ্ছেদ বেশি",
      len(pl2["paragraphs"]) > len(pl1["paragraphs"]))
check("পূর্ণ পরিধিতে প্রশ্ন বেশি",
      len(pl2["review_questions"]) > len(pl1["review_questions"]))

# ধরন ৩ — প্রচ্ছন্ন
p3 = AuditProfile(is_deemed=True, has_register=True, has_export_data=True)
pl3 = assemble_report_plan(p3, ALL_F)
k3 = {f["kind"] for f in pl3["findings"]}
check("প্রচ্ছন্নে গন্তব্য-অসঙ্গতি বাদ (সরাসরির বিষয়)",
      "destination_mismatch" not in k3)
check("প্রচ্ছন্নে প্রচ্ছন্ন-ফাইন্ডিং আসে",
      "deemed_export_doc_incomplete" in k3)
check("প্রচ্ছন্নে সরবরাহ-অনুচ্ছেদ আসে",
      any("প্রচ্ছন্ন রপ্তানি" in t for t in pl3["paragraphs"]))

# ধরন ৪ — ইপিজেড (ইউপি নয়)
p4 = AuditProfile(is_epz=True, has_register=True, has_export_data=True)
pl4 = assemble_report_plan(p4, ALL_F)
k4 = {f["kind"] for f in pl4["findings"]}
check("ইপিজেডে ইউপি-নির্ভর ফাইন্ডিং বাদ",
      "up_arithmetic" not in k4 and "export_without_up" not in k4)
check("ইপিজেডে আইপি/ইপি অনুচ্ছেদ আসে",
      any("আইপি/ইপি" in t for t in pl4["paragraphs"]))
check("ইপিজেডে ইউপি অনুচ্ছেদ বাদ",
      not any(t.startswith("ইউটিলাইজেশন পারমিশনের") for t in pl4["paragraphs"]))
check("ইপিজেডে ইউপি-প্রশ্ন বাদ",
      not any("ইউপি" in q for q, _, _ in pl4["review_questions"]))

# পোশাক শিল্প — ইউডি, ইউপি নয়
p5 = AuditProfile(is_rmg=True, has_register=True)
check("পোশাক শিল্পেও ইউপি-নির্ভর ছাঁচ প্রযোজ্য নয়",
      not template_applies("up_arithmetic", p5))

check("শূন্য ফাইন্ডিং দিলে কিছুই আসে না",
      assemble_report_plan(p2, [])["findings"] == [])

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "❌ FAILURES")
sys.exit(0 if _all_ok else 1)
