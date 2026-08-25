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
| C2 | বর্ধিত প্রাপ্যতা [বিধি ৮] + বিয়োজন যাচাই | ✅ **সম্পন্ন** | `EntitlementRow.extended_entitlement` + `effective_entitled_quantity`; `Rule8Observation` + `_build_rule8_observations`; test `tests/test_extended_entitlement_c2.py`। ↓ "চ. অগ্রগতি" |
| C3 | ক্যাপাসিটির **তৃতীয় উৎস — বন্ড লাইসেন্স** | ✅ **সম্পন্ন** | `compute_warehouse_capacity(bond_license_capacity_mt=...)` — অগ্রাধিকার + cross-check; test `tests/test_bond_license_capacity_c3.py` (১৬/১৬ pass)। ↓ "চ. অগ্রগতি" |
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

### ✅ C3 — বন্ড লাইসেন্স = তৃতীয় ক্যাপাসিটি উৎস — সম্পন্ন

`capacity_ledger.py`-তে `compute_warehouse_capacity()` এ নতুন
`bond_license_capacity_mt` ইনপুট + engine-এ `bond_license_capacity_mt` param:

- **উৎস অগ্রাধিকার:** (১) বন্ড লাইসেন্সের ধারণক্ষমতা → (২) প্রদত্ত মান →
  (৩) ওয়্যারহাউস মাপ হইতে গণনা। লাইসেন্স-সংখ্যা official বিধায় মাপ/প্রদত্ত
  থাকিলেও তাহাই চূড়ান্ত (নিরীক্ষক নির্দেশ; Gold Shine ৩,৪০০ মে.টন)।
- **স্বচ্ছতা:** `WarehouseCapacity.source` = `bond_license` এবং একাধিক উৎস
  ভিন্ন মান দিলে formula-তে "⚠ ভিন্ন মান বিদ্যমান … যাচাই আবশ্যক" সতর্কতা।
- **regime অক্ষত:** পুরাতন → min(প্রাপ্যতা÷৩, লাইসেন্স); নূতন (০১.০৭.২০২৬+) →
  লাইসেন্স। engine নিরীক্ষা-মেয়াদ দেখিয়া regime নির্ধারণ করে (পূর্ববৎ)।
- **যাচাই:** `tests/test_bond_license_capacity_c3.py` — ৭ কেস, ১৬টি assertion
  সব pass; পূর্বের measured/given/missing আচরণ অক্ষত (regression)।

### ✅ চলমান অ্যাপ (FastAPI + UI) — Module 1 এখন সত্যিই চলে

engine আর headless নয় — `backend/api/main.py` (FastAPI) + `backend/api/static/`
(লোকাল UI) একই process-এ:

- **এন্ডপয়েন্ট:** `POST /api/analyze/import` (প্রাপ্যতা+আমদানি → ৫ দাবিসহ JSON),
  `POST /api/analyze/import/xlsx` (১০-শীট Excel কার্যপত্র), `GET /` (UI), `/api/health`।
- **UI:** ফাইল আপলোড + প্যারামিটার (নতুন প্রাপ্যতা তারিখ, বন্ড লাইসেন্স/ওয়্যারহাউস
  ধারণক্ষমতা) → দাবির সারসংক্ষেপ (stat cards) + সতর্কতা + বিস্তারিত টেবিল।
- **চালানো:** `cd backend && python3 run_server.py` → http://localhost:4800 (LAN/মোবাইলেও)।
- **যাচাই (sandbox, TestClient):** sample_full.xlsx — analyze 200 (৮ প্রাপ্যতা, ১৪ আমদানি,
  দাবি ২ ৳১০.৬৮ লক্ষ, সর্বমোট ৳৫০.২ লক্ষ), xlsx 200 (২২KB), UI/app.js 200।
- **সীমা:** দাবি ৩ কনজাম্পশন-রেজিস্টার সাপেক্ষ; Excel-এ দাবি ৫ শীট এখনো নেই; OCR/
  Level-2 AI/Module 2–6 বাকি।

### ✅ Excel কার্যপত্রে দাবি ৫ শীট — যুক্ত

`report_writer.py`: নতুন শীট **"২ক. মেয়াদোত্তর আমদানি"** (অননুমোদিত ও বন্ডিং
ক্যাপাসিটির মাঝে) — `COLS_POST_PERIOD` (২০ কলাম: উৎস/HS/পণ্য/বিল/পরিমাণ/
পূর্ণ BE বিভাজন/সময়কাল/আইনি ভিত্তি) + `_sheet_post_period()`। cover (০.
সারসংক্ষেপ)-এ "দাবি ৫" সারি যুক্ত; সর্বমোট SUM স্বয়ংক্রিয়ভাবে দাবি ৫ ধরে।
যাচাই: post-period রেকর্ডসহ workpaper — শীট + ৩ রেকর্ড + total, cover-এ দাবি ৫।

### ✅ C2 — বর্ধিত প্রাপ্যতা [বিধি ৮] + বিয়োজন যাচাই — সম্পন্ন

- **সীমা:** `EntitlementRow.extended_entitlement` + `effective_entitled_quantity`
  (= মূল + বর্ধিত)। excess/utilization/FIFO/assess_excess সব **মোট অনুমোদিত**-এর
  বিপরীতে (extended=0 হইলে আচরণ অপরিবর্তিত — folded শীটও কাজ করে)।
- **বিয়োজন পর্যবেক্ষণ (দাবি নহে):** `Rule8Observation` + `_build_rule8_observations`।
  extension_applies flag বা কোনো এককে extended>0 থাকিলে — সামগ্রিক নির্দেশ
  (নিরীক্ষক স্ব-ঘোষণা তলব → বন্ড রেজিস্টারে যাচাই → বিয়োজন নিশ্চিত) + আইটেমভিত্তিক
  সারি; instruction warnings-এও যায় (Excel "৮. সতর্কতা" ও UI-তে দৃশ্যমান)।
  **কোনো রাজস্ব যোগ করে না** — শুধু পর্যবেক্ষণ/নির্দেশ।
- **API/UI:** `extension_applies` form param + UI checkbox + "৩ক. বিধি ৮" কার্ড।
- **যাচাই:** `tests/test_extended_entitlement_c2.py` — ৩ কেস (Gold Shine combined
  ১৪১১.০৮৫ / excess ১৪১.২৯১; flag-only; regression), সব pass; API flag verified।
- **সীমা:** data_loader এখনো শীট থেকে পৃথক বর্ধিত-কলাম পার্স করে না — folded শীট বা
  extension flag দিয়ে চলে; পৃথক-কলাম loader-সাপোর্ট পরবর্তী কাজ।

### ✅ JS চেক-ক্যাটালগ Python engine-এ পোর্ট — সম্পন্ন

নিরীক্ষকের JS ওয়ার্কবেঞ্চের পুরো ম্যানুয়াল-চেক ইঞ্জিন Python-এ আনা হলো:

- **`services/checks/numeric.py`** — ৯টি reconciliation চেক (entitlement, B/E-vs-
  register raw/machinery/sample, coefficient, UD/EP-vs-export, material-balance,
  wastage, **overstay ২ বছর — C7**)। দ্বিমুখী (ঘাটতি→দাবি; over-record→রেকর্ড
  অসঙ্গতি, রাজস্ব ০); duty ঐচ্ছিক।
- **`services/checks/validity.py`** — লাইসেন্স মেয়াদ, UP/UD coverage, HS entitlement।
- **`services/checks/evidence.py`** — Smart Evidence Chip (OCR টেক্সট → সংখ্যা +
  বাংলা/English synonym দুই-স্তর field-সাজেশন + confidence)।
- **`knowledge/check_specs.py`** — serializable spec + legal-ref map।
- **API:** `/api/checks/specs`, `/api/checks/numeric`, `/api/checks/validity`,
  `/api/checks/evidence/scan`। **UI:** "🧮 ম্যানুয়াল যাচাই" view (numeric+validity
  ফর্ম + compute + Evidence paste-panel)।
- **দ্বৈত গণনা রোধ:** এই উপমোট চূড়ান্ত রাজস্ব-মোটে auto-যোগ হয় না; source-ট্যাগড
  finding নিরীক্ষক গ্রহণ করলে যোগ হয়।
- **যাচাই:** `tests/test_manual_checks.py` (২৯) + `tests/test_evidence_chips.py`
  (৮) — JS test হইতে পোর্ট, সব pass; UI browser-এ যাচাইকৃত।

এতে **C7 (overstay)** ও Module 2/3/4-এর মূল চেক-সূত্র (coefficient, material-
balance, wastage, UD-export) engine-এ চলে এলো (ম্যানুয়াল-ইনপুট রূপে; পরে
ফাইল-স্বয়ংক্রিয় নিষ্কাশনের সাথে যুক্ত হবে)।

**পরবর্তী:** এই চেকগুলো ফাইল-বিশ্লেষণের সাথে auto-ইনপুট (register/AIS হইতে) → OCR
স্তর → Module 2 পূর্ণ।

### ✅ C7 — মেয়াদোত্তীর্ণ (overstay) = দাবি ৬ (engine, সর্বমোটে যুক্ত) — সম্পন্ন

নিরীক্ষক সিদ্ধান্ত: overstay পৃথক দাবি, সর্বমোটে auto-যোগ (manual চেক ছাড়াও)।

- **`OverstayRecord` + `_build_overstay`** (`import_analysis.py`) — বন্ড রেজিস্টার
  (তফসিল-১) এর প্রতি-সারি ইন্টু/এক্স-বন্ড linkage হইতে অবশিষ্ট = into − ex(same row);
  ইন্টু-বন্ড তারিখ কর্তন-সীমার (as-of − `overstay_years`, default ২.০) আগে ও
  অবশিষ্ট > 0 হইলে overstay। শুল্ক AIS/MIS বিল হইতে আনুপাতিক (assess_bill)।
- **সর্বমোটে যুক্ত:** summary-তে "দাবি ৬" + সর্বমোট; Excel-এ "২খ. মেয়াদোত্তীর্ণ
  কাঁচামাল" শীট + cover-এ দাবি ৬; UI-তে stat card + টেবিল। রেজিস্টার না থাকিলে
  "স্থগিত" নোট → ম্যানুয়াল overstay চেক নির্দেশ।
- **threshold:** ২ বছর = working default (gazette citation অপেক্ষমাণ), `overstay_years`
  প্যারামিটারাইজড।
- **যাচাই:** `tests/test_overstay_c7.py` — ৮ assertion (৩০০ kg→৳৩০,০০০, cutoff,
  সর্বমোট, no-register warning, ৫-বছর threshold), সব pass; Excel/cover যাচাইকৃত;
  ৬টি prior suite regression green।

HANDOFF §২খ: **C1 ✅ C2 ✅ C3 ✅ C6 ✅ C7 ✅** | বাকি: C4 (EPZ IP/EP), C5 (বিদ্যুৎ), C8 (PRC)।
