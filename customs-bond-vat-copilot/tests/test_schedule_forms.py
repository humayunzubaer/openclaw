"""
তফসিল-ছক প্রযোজ্যতা ম্যাপিং — regression test.

চালান:  python3 tests/test_schedule_forms.py

যাচাই করে:
  • সরাসরি (পোশাক ব্যতীত)  → ৪টি ছক: তফসিল-১, ২, ৩ ছক-ক, ৪
  • প্রচ্ছন্ন (পোশাক ব্যতীত) → ৫টি ছক: তফসিল-১, ২, ৩ ছক-খ, ৪, ৫
  • তফসিল-৫ ও তফসিল-৩ ছক-খ কখনো সরাসরি প্রতিষ্ঠানে যায় না
  • বার্ষিক নিরীক্ষায় দাখিলযোগ্য বিবরণী: সরাসরি ২টি, প্রচ্ছন্ন ৩টি
  • ইপিজেডে ইউপি-নির্ভর ছক 'শর্তসাপেক্ষ' চিহ্নিত (আইপি/ইপি প্রতিস্থাপন)
  • পোশাক শিল্পে এসআরও ২১৩ এর ৫ তফসিল; যুগপৎ হলে ২১২-এর প্রচ্ছন্ন ছক যুক্ত
  • build_requisition-এ schedules যুক্ত হয় ও চাহিদাপত্রে রেন্ডার হয়
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.doc_requisition import (
    EntityType, applicable_schedules, build_requisition, render_requisition,
    SRO212_SCHEDULES, SCHEDULE_STATUS_CONDITIONAL,
)

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


def labels(scheds):
    return [s.label for s in scheds]


print("CASE 1 — সরাসরি রপ্তানিমুখী (পোশাক ব্যতীত): ৪টি ছক")
d = applicable_schedules(EntityType.NON_EPZ_DIRECT)
check("মোট ৪টি ছক", len(d) == 4)
check("তালিকা = তফসিল-১, ২, ৩ ছক-ক, ৪",
      labels(d) == ["তফসিল-১", "তফসিল-২", "তফসিল-৩ ছক-ক", "তফসিল-৪"])
check("তফসিল-৫ নাই (প্রচ্ছন্নের ছক)", "তফসিল-৫" not in labels(d))
check("তফসিল-৩ ছক-খ নাই", "তফসিল-৩ ছক-খ" not in labels(d))
check("বার্ষিক দাখিলযোগ্য ২টি", sum(1 for s in d if s.annual_return) == 2)

print("CASE 2 — প্রচ্ছন্ন রপ্তানিমুখী: ৫টি ছক")
m = applicable_schedules(EntityType.NON_EPZ_DEEMED)
check("মোট ৫টি ছক", len(m) == 5)
check("তালিকা = তফসিল-১, ২, ৩ ছক-খ, ৪, ৫",
      labels(m) == ["তফসিল-১", "তফসিল-২", "তফসিল-৩ ছক-খ", "তফসিল-৪", "তফসিল-৫"])
check("তফসিল-৩ ছক-ক নাই (সরাসরির ছক)", "তফসিল-৩ ছক-ক" not in labels(m))
check("বার্ষিক দাখিলযোগ্য ৩টি", sum(1 for s in m if s.annual_return) == 3)

print("CASE 3 — উৎস-তালিকার অখণ্ডতা")
check("SRO212_SCHEDULES-এ ৬টি ছক (৫ তফসিল, ৩ দুই ছকে)", len(SRO212_SCHEDULES) == 6)
check("পাঁচটি স্বতন্ত্র তফসিল",
      len({s.schedule for s in SRO212_SCHEDULES}) == 5)
check("তফসিল-১ = ১৬ কলাম",
      any(s.schedule == "তফসিল-১" and s.columns == 16 for s in SRO212_SCHEDULES))
check("তফসিল-৩ উভয় ছক = ১৭ কলাম",
      all(s.columns == 17 for s in SRO212_SCHEDULES if s.schedule == "তফসিল-৩"))

print("CASE 4 — ইপিজেড: ইউপি-নির্ভর ছক শর্তসাপেক্ষ")
e = applicable_schedules(EntityType.EPZ_DIRECT)
check("ইপিজেড সরাসরিও ৪টি ছক", len(e) == 4)
cond = [s for s in e if s.status == SCHEDULE_STATUS_CONDITIONAL]
check("অন্তত ১টি শর্তসাপেক্ষ চিহ্নিত", len(cond) >= 1)
check("তফসিল-২ (ইউপি ফরম) শর্তসাপেক্ষ",
      any(s.schedule == "তফসিল-২" and s.status == SCHEDULE_STATUS_CONDITIONAL for s in e))
check("শর্তসাপেক্ষে আইপি/ইপি ব্যাখ্যা আছে",
      all("আইপি" in s.note for s in cond))
check("শর্তসাপেক্ষের certainty = E (অনুমিত)", all(s.certainty == "E" for s in cond))
check("তফসিল-১ (রেজিস্টার) অপরিবর্তিত প্রযোজ্য",
      any(s.schedule == "তফসিল-১" and s.status == "প্রযোজ্য" for s in e))

print("CASE 5 — পোশাক শিল্প: এসআরও ২১৩")
r = applicable_schedules(EntityType.RMG_DIRECT)
check("৫টি তফসিল", len(r) == 5)
check("সব এসআরও ২১৩", all("২১৩" in s.sro for s in r))
r2 = applicable_schedules(EntityType.RMG_DIRECT, also_deemed=True)
check("যুগপৎ হলে ২১২-এর প্রচ্ছন্ন ছক যুক্ত", len(r2) > len(r))
check("যুক্ত অংশ শর্তসাপেক্ষ",
      all(s.status == SCHEDULE_STATUS_CONDITIONAL
          for s in r2 if "২১২" in s.sro))

print("CASE 6 — চাহিদাপত্রে সংযুক্তি ও রেন্ডার")
req = build_requisition(EntityType.NON_EPZ_DIRECT, company_name="নমুনা লিমিটেড",
                        period_from=date(2025, 1, 1), period_to=date(2025, 12, 31))
check("req.schedules = ৪টি", len(req.schedules) == 4)
check("annual_return_schedules = ২টি", len(req.annual_return_schedules) == 2)
txt = render_requisition(req)
check("রেন্ডারে তফসিল-ছক অনুচ্ছেদ", "【প্রযোজ্য তফসিল-ছক】" in txt)
check("রেন্ডারে ছক-ক উল্লেখ", "তফসিল-৩ ছক-ক" in txt)
check("রেন্ডারে ছক-খ নাই", "তফসিল-৩ ছক-খ" not in txt)
check("দ্রষ্টব্যে সারসংক্ষেপ", "প্রযোজ্য তফসিল-ছক: মোট ৪টি" in txt)

req_d = build_requisition(EntityType.NON_EPZ_DEEMED)
check("প্রচ্ছন্ন চাহিদাপত্রে ৫টি", len(req_d.schedules) == 5)
check("প্রচ্ছন্ন রেন্ডারে তফসিল-৫", "তফসিল-৫" in render_requisition(req_d))

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "❌ FAILURES")
sys.exit(0 if _all_ok else 1)
