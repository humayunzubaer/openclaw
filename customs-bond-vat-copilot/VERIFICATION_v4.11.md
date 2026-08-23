# v4.11 Engine Verification — যাচাই প্রতিবেদন

> কোড পড়ে (grep নয়, প্রকৃত লজিক) নিশ্চিত করা "done vs pending" অবস্থা।
> ভিত্তি: `backend/services/import_analysis.py`, `capacity_ledger.py`,
> `bonding_rules.py`, `schedule3_analyzer.py`, `doc_requisition.py`,
> `interest_penalty.py`। উদ্ধৃত line নম্বর v4.11 কোড অনুযায়ী।

তারিখ: ২০২৬-০৮-২৩ · যাচাইকারী: Claude Code

---

## ক. Import Analysis Engine — যা প্রকৃতপক্ষে বাস্তবায়িত (✅)

মূল engine-টি শক্ত ভিত্তির উপর দাঁড়ানো। `analyze()` (`import_analysis.py:716`)
৭ ধাপে চলে এবং summary-তে (`:1720-1744`) **ঠিক ৪টি পৃথক দাবি** গণনা করে:

| দাবি | বিষয় | মূল কোড |
|---|---|---|
| দাবি ১ | অননুমোদিত এইচএস কোড — পূর্ণ BE শুল্ক-কর | `_build_unauthorized` `:1096` |
| দাবি ২ | প্রাপ্যতার অতিরিক্ত — FIFO আনুপাতিক (+ ক্লাস্টার) | `_build_excess_and_utilization` `:911`, `assessment.assess_excess` |
| দাবি ৩ | এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন — shield/ledger | `_check_bonding_capacity` `:1322` |
| দাবি ৪ | বিধি ১১(১) উৎপাদন ক্ষমতার ৮০% সীমা | `check_capacity_limit` (`bonding_rules.py:300`) |

অন্যান্য বাস্তবায়িত বৈশিষ্ট্য (verified):
- **শূন্য সহনসীমা** (`TOLERANCE=0.0`, `:55`)
- **এককালীন ক্যাপাসিটি সূত্র** `min((প্রাপ্যতা+মজুত)÷৩, ধারণক্ষমতা)`; ০১.০৭.২০২৬
  হইতে শুধু ধারণক্ষমতা; straddle মেয়াদ খণ্ডন — `bonding_rules.determine_regime`
  `:150`, `resolve_capacity` `:186`, `NEW_REGIME_DATE`
- **Shield/ledger** — সময়ানুক্রমিক into-bond/ex-bond, per-event লঙ্ঘন, দ্বৈত
  শুল্কায়ন নয় — `capacity_ledger.build_capacity_ledger`
- **ক্লাস্টার read-only** — engine নিজে ক্লাস্টার বানায় না (`allow_cluster=False` `:749`)
- **সামগ্রিক (aggregate) ক্যাপাসিটি যাচাই — কেজিতে**, per-item নয় (`:1365-1366`)
- **ভুল-মেয়াদ ফাইল সনাক্ত** (`_validate_period_coverage` `:847`, coverage<0.5 → ⛔)
- **মেশিনারিজ বাদ**, **একক নিষ্কাশন** (kg vs sheet unit), **register-gated**
  (কনজাম্পশন রেজিস্টার না থাকিলে ক্যাপাসিটি যাচাই স্থগিত — `:1341`)
- **স্থানীয় ক্রয়ে ১৫% উৎসে মূসক** (`source_vat_demanded`)

## খ. অন্যান্য বাস্তবায়িত মডিউল (✅ — engine-এর বাইরে)

- **Schedule-3 analyzer** — ১১টি আন্তঃকলাম যাচাই (T-01/T-04/T-06/T-08 ...)
- **Interest/Penalty** — কাস্টমস আইন ২০২৩ ধারা ৩২ (মাসিক ১%, ≤২৪ মাস)
- **Doc requisition** — ৫ শ্রেণির চাহিদাপত্র (EPZ/non-EPZ × direct/deemed + RMG)
- **SRO-213 RMG** বিধিমালা বিশ্লেষণ · **report_writer** (১০-শীট Excel)
- **matcher** (৫-স্তর) · **agent + agent_tools** · **bijoy** (Unicode→SutonnyMJ)
- **network_access** (LAN + Tailscale + PIN) · **learned_rules / kb_loader / legal_scope**

---

## গ. HANDOFF §২খ-র ৮টি সংশোধন — প্রকৃত অবস্থা

| # | সংশোধন | অবস্থা | প্রমাণ |
|---|---|---|---|
| C1 | মেয়াদোত্তর আমদানি = **পৃথক দাবি** | ✅ **সম্পন্ন** (দাবি ৫) | `_build_post_period` + `_is_post_period`; test `tests/test_post_period_c1.py` (১৬/১৬ pass)। ↓ "চ. অগ্রগতি" দ্রষ্টব্য |
| C2 | বর্ধিত প্রাপ্যতা [বিধি ৮] + বিয়োজন যাচাই | ❌ **নেই** | `EntitlementRow`-এ extended/বিয়োজন ফিল্ড নেই (`:76-129`); শুধু `doc_requisition.py:161` লাইনে চাওয়া হয় |
| C3 | ক্যাপাসিটির **তৃতীয় উৎস — বন্ড লাইসেন্স** | ❌ **নেই** | `resolve_capacity`/`compute_one_time_capacity` কেবল warehouse/sheet জানে (`bonding_rules.py:186-262`) |
| C4 | EPZ শাখা — CBMS/IP/EP যাচাই | ⚠️ **আংশিক** | `doc_requisition`-এ EPZ শ্রেণি ও পৃথক দলিল-তালিকা আছে; engine-এ IP/EP পরিমাণ ক্রস-চেক নেই |
| C5 | বিদ্যুৎ-উৎপাদন সামঞ্জস্য যাচাই | ❌ **নেই (engine)** | শুধু `doc_requisition.py:261` লাইন; প্রতি-কেজি বিদ্যুৎ-ব্যয় check নেই |
| C6 | মূল্য সংযোজনের হার গণনা | ✅ **আছে** | `schedule3_analyzer._check_value_addition` T-06 ≥১৫% (`:380-407`) |
| C7 | T-03 মজুদকাল (২৪ মাস) + T-06 (≥১৫%) | 🟡 **অর্ধেক** | T-06 আছে; T-03 মজুদকাল (২৪ মাস) কোথাও নেই |
| C8 | PRC/প্রত্যাবাসন যাচাই | ⚠️ **আংশিক** | `schedule3._check_repatriation` T-08 (১২০ দিন) আছে; পূর্ণ PRC/export-realization মডিউল নেই |

**স্কোর:** সম্পূর্ণ ১টি (C6) · অর্ধেক/আংশিক ৩টি (C4, C7, C8) · হয়নি ৪টি (C1, C2, C3, C5)

---

## ঘ. ★ Memory-র সাথে গুরুত্বপূর্ণ অমিল (সৎ সতর্কতা)

Project memory বলছিল **v4.9**-এ correction 1/2/3/6 সম্পন্ন, এবং সেখানে
`value_addition.py` ও `electricity_consistency.py` নামে ফাইল ছিল।

এই আপলোড করা **v4.11-এ ঐ দুটো ফাইলের কোনোটিই নেই** — বরং ভিন্নভাবে সাজানো
(`schedule3_analyzer.py`, `interest_penalty.py`, `doc_requisition.py`,
`sro213_rmg.py`)। যাচাইয়ে দেখা যায় **কেবল C6-ই প্রকৃতপক্ষে উপস্থিত**;
C1/C2/C3 এই কোডে নেই।

অর্থাৎ আপলোড করা v4.11 আর memory-বর্ণিত v4.9 **একই ধারার নয়** — আলাদা
refactor/branch। **কোডই চূড়ান্ত সত্য** — তাই এই তালিকা অনুযায়ীই কাজ এগোনো
উচিত, memory-র দাবি অনুযায়ী নয়।

---

## ঙ. প্রস্তাবিত ক্রম (revenue-impact + স্পষ্টতা অনুযায়ী)

1. **C1 — মেয়াদোত্তর আমদানি** (Gold Shine ৩৬৮ মে.টন → ~৳৩৫ লক্ষ; স্পষ্ট স্পেক)
2. **C3 — বন্ড লাইসেন্স ক্যাপাসিটি উৎস** (Gold Shine ৩,৪০০ মে.টন; ছোট, নির্দিষ্ট)
3. **C2 — বর্ধিত প্রাপ্যতা [বিধি ৮] + বিয়োজন** (self-declaration → auditor যাচাই)
4. **C7 T-03 মজুদকাল ২৪ মাস**, তারপর **C5 বিদ্যুৎ**, **C4 EPZ IP/EP**, **C8 PRC**

প্রতিটি সংশোধনের আগে সংশ্লিষ্ট ডোমেইন-নিয়মের gazette-সঠিক সংখ্যা নিরীক্ষকের
থেকে নিশ্চিত করা হবে (working default আইনি সূত্র হিসেবে ব্যবহার নিষিদ্ধ)।

---

## চ. অগ্রগতি লগ

### ✅ C1 — মেয়াদোত্তর আমদানি (দাবি ৫) — সম্পন্ন

নিরীক্ষক-নিশ্চিতকৃত নিয়ম অনুযায়ী `import_analysis.py`-তে বাস্তবায়িত:

- **নতুন পঞ্চম দাবি** — `PostPeriodRecord` + `_build_post_period()`; summary-তে
  "দাবি ৫ — মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি" এবং সর্বমোটে যুক্ত।
- **বিল-পরিসর:** `period_to < bill_date < next_entitlement_date`
  (নিরীক্ষক "নতুন প্রাপ্যতা তারিখ" ইনপুট দেবেন)। তারিখ না দিলে period_to-এর
  পরের সব বিল ধরা হয় + সতর্কতা। প্রাক-মেয়াদ বিল **বাদ**।
- **শুল্কায়ন:** আমদানিতে পূর্ণ BE (CD+RD+SD+VAT+AT+AIT, `assess_full`);
  স্থানীয় ক্রয়ে ১৫% উৎসে মূসক (নিরীক্ষক Q3: একসাথে)।
- **দ্বৈত দাবি রোধ:** matching-এর আগে post-period বিল পৃথক করা হয় — তাই
  excess/অননুমোদিত/ক্যাপাসিটি কোনো হিসাবে আসে না, কেবল দাবি ৫-এ।
- **আইনি ভিত্তি:** এসআরও ২১৪-আইন/২০২৪ — বিধি ৫, ৯, ১২; ব্যাংক গ্যারান্টি নোটসহ।
- **যাচাই:** `tests/test_post_period_c1.py` — ৩ কেস, ১৬টি assertion, সব pass
  (Gold Shine প্যাটার্ন: মেয়াদোত্তর import → পৃথক দাবি; regression: in-period
  দাবি ১/২ অক্ষত)।

**পরবর্তী:** C3 (বন্ড লাইসেন্স ক্যাপাসিটি উৎস) → C2 (বর্ধিত প্রাপ্যতা [বিধি ৮])।
