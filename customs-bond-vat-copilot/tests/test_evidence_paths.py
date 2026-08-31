"""
বিকল্প প্রমাণ-পথ — regression test.

চালান:  python3 tests/test_evidence_paths.py

  ১. প্রতিটি অনুপস্থিত দলিলের বিকল্প উৎস ও সীমা আছে
  ২. ★ নিষিদ্ধ দাবি-ছাঁচের নাম প্রকৃত OPINION_TEMPLATES-এ আছে (typo প্রহরী)
  ৩. প্রমাণাভাবে দাবি ছাঁকা হয় — অহেতুক দাবিনামা রোধ
  ৪. দলিল থাকিলে কিছুই অবরুদ্ধ হয় না
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.evidence_paths import (
    EVIDENCE_PATHS, DOC_LABELS, audit_route, blocked_demand_kinds,
    filter_findings, path_for, paths_for,
    DOC_REGISTER, DOC_UP, DOC_EXPORT, DOC_COEFFICIENT, DOC_MIS_IMPORT,
)
from knowledge.report_style import OPINION_TEMPLATES

_all_ok = True


def check(name, cond):
    global _all_ok
    print(("  ✅ " if cond else "  ❌ ") + name)
    _all_ok = _all_ok and bool(cond)


print("== ১. ছকের অখণ্ডতা ==")
check("১৩টি দলিলের পথ আছে", len(EVIDENCE_PATHS) == 13)
check("সব দলিলের বাংলা নাম আছে",
      all(d in DOC_LABELS for d in EVIDENCE_PATHS))
check("প্রতিটিতে বিকল্প উৎস আছে",
      all(p.alternatives for p in EVIDENCE_PATHS.values()))
check("প্রতিটিতে 'সাধারণত কী প্রমাণ করে' আছে",
      all(p.normally_proves for p in EVIDENCE_PATHS.values()))
check("প্রতিটিতে আইনি ভিত্তি আছে",
      all(p.legal_ref for p in EVIDENCE_PATHS.values()))
blocking = [p for p in EVIDENCE_PATHS.values() if p.blocked_kinds]
check("যেখানে যাচাই অবরুদ্ধ সেখানে তলব ও প্রস্তাব দুইই আছে",
      all(p.requisition and p.proposal for p in blocking))

print("== ২. ★ নিষিদ্ধ ছাঁচের নাম যাচাই (typo প্রহরী) ==")
all_blocked = set()
for p in EVIDENCE_PATHS.values():
    all_blocked.update(p.blocked_kinds)
unknown = sorted(k for k in all_blocked if k not in OPINION_TEMPLATES)
check(f"সব নিষিদ্ধ ছাঁচ প্রকৃত ({len(all_blocked)}টি)"
      + (f" — অজানা: {unknown}" if unknown else ""), not unknown)

print("== ৩. রেজিস্টার নাই — কী হয় ==")
r = audit_route([DOC_REGISTER])
bk = set(r["blocked_kinds"])
check("এককালীন ক্যাপাসিটির দাবি অবরুদ্ধ", "capacity_breach_demand" in bk)
check("overstay দাবি অবরুদ্ধ", "overstay_demand" in bk)
check("ইন্টু-বন্ড বিলম্ব অবরুদ্ধ", "into_bond_delay" in bk)
check("তবু প্রাপ্যতার অতিরিক্ত নির্ণেয়",
      any("দাবি ২" in s for s in r["still_possible"]))
check("তবু অননুমোদিত এইচ.এস নির্ণেয়",
      any("দাবি ১" in s for s in r["still_possible"]))
check("রেজিস্টার তলবের নির্দেশ আছে",
      any("রেজিস্টার" in q for q in r["requisitions"]))
check("প্রস্তাবনায় শর্তভঙ্গ যায় (দাবি নয়)",
      any("বিধি ৭" in p for p in r["proposals"]))
check("প্রস্তাবে 'করা যেতে পারে' ভাষা",
      all("যেতে পারে" in p for p in r["proposals"]))

print("== ৪. ★ অহেতুক দাবি রোধ ==")
findings = [
    {"kind": "excess_import_demand", "para": "৩৬"},
    {"kind": "unauthorized_hs_demand", "para": "৩৫"},
    {"kind": "capacity_breach_demand", "para": "৩৭"},
    {"kind": "overstay_demand", "para": "৩৮"},
    {"kind": "into_bond_delay", "para": "১৯"},
]
res = filter_findings(findings, [DOC_REGISTER])
kept = {f["kind"] for f in res["kept"]}
sup = {s["kind"] for s in res["suppressed"]}
check("প্রমাণসিদ্ধ দাবি টিকে থাকে",
      kept == {"excess_import_demand", "unauthorized_hs_demand"})
check("প্রমাণহীন দাবি ছাঁকা হয়",
      sup == {"capacity_breach_demand", "overstay_demand", "into_bond_delay"})
check("ছাঁকার কারণ লিপিবদ্ধ",
      all("প্রমাণ ব্যতিরেকে" in s["কারণ"] for s in res["suppressed"]))

print("== ৫. ইউপি ও রপ্তানি নাই ==")
r2 = audit_route([DOC_UP, DOC_EXPORT])
bk2 = set(r2["blocked_kinds"])
for k in ["up_arithmetic", "value_addition_short", "export_without_up",
          "repatriation_overdue", "destination_mismatch"]:
    check(f"অবরুদ্ধ: {k}", k in bk2)

print("== ৬. সহগ নাই — বিকল্প পথ ==")
p = path_for(DOC_COEFFICIENT)
check("সমজাতীয় সহগের ৩০-দিন বিকল্প উল্লিখিত",
      any("সমজাতীয়" in a and "৩০" in a for a in p.alternatives))
check("মূসক-৪.৩ বিকল্প হিসেবে আছে",
      any("৪.৩" in a for a in p.alternatives))
check("তাত্ত্বিক ব্যবহার তবু আনুমানিক নির্ণেয়",
      any("তাত্ত্বিক" in s for s in p.still_possible))
check("সহগ-অতিরিক্ত ব্যবহারের দাবি নিষিদ্ধ",
      "coefficient_overuse" in p.blocked_kinds)
check("নিশ্চয়তা 【E】-তে নামে", p.certainty == "E")

print("== ৭. প্রান্তিক অবস্থা ==")
check("দলিল সব থাকিলে কিছুই অবরুদ্ধ নয়", blocked_demand_kinds([]) == set())
check("সব দলিল থাকিলে সব দাবি টিকে",
      len(filter_findings(findings, [])["kept"]) == len(findings))
check("অজানা দলিল-নাম উপেক্ষিত", paths_for(["অজানা_দলিল"]) == [])
check("এমআইএস নাই — কোনো দাবি অবরুদ্ধ নয় (বিকল্প যথেষ্ট)",
      blocked_demand_kinds([DOC_MIS_IMPORT]) == set())

print()
print("RESULT:", "ALL PASS ✅" if _all_ok else "❌ FAILURES")
sys.exit(0 if _all_ok else 1)
