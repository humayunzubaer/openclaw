# MASTER HANDOFF — কাস্টমস বন্ড ও ভ্যাট অডিট ইন্টেলিজেন্স প্ল্যাটফর্ম

> **এই একটি ফাইল + সঙ্গের কোড পড়লেই যেকোনো AI মডেল প্রকল্পটি এখান থেকে ধরে শেষ করতে পারবে।**
> এটি একক প্রবেশদ্বার (single source of truth)। পুরনো `HANDOFF_v4.md` ও
> `VERIFICATION_v4.11.md` ঐতিহাসিক রেফারেন্স — বিরোধ হলে **এই ফাইল চূড়ান্ত**।
>
> সংস্করণ: v4.11+ · হালনাগাদ: ২০২৬-০৮-২৫ · ভাষা নীতি: আউটপুট **বাংলা (প্রমিত চলিত)**,
> technical term ইংরেজিতে।

---

## ০. এক নজরে (TL;DR for the next AI)

- **কী:** বাংলাদেশ কাস্টমস **বন্ডেড ওয়্যারহাউস** ও **ভ্যাট** নিরীক্ষার ৯০–৯৫% কাজ
  **অফলাইনে** স্বয়ংক্রিয় করার সফটওয়্যার।
- **স্ট্যাক (canonical):** Python **FastAPI** backend (`backend/`) + vanilla-JS **PWA**
  frontend (`backend/api/static/` চালু UI; `public/` ও `src/` পুরনো JS PWA — reference)।
  চালাতে: `cd backend && python3 run_server.py` → http://localhost:4800
- **মূল engine:** `backend/services/import_analysis.py` (`analyze()` → **৬টি পৃথক দাবি**)।
- **জ্ঞানভান্ডার (KB):** `backend/knowledge/kb/` — ১৫ মডিউল + `08_RULES_ENGINE.json`,
  `kb_loader.py` দিয়ে লোড হয় (১৪ test, ১১ instrument, ১৫ দলিল, ৭ constraint)।
- **অকাট্য নীতি:** আইনি threshold সংখ্যা **কখনো আন্দাজ/বানানো নয়** — gazette citation ছাড়া নয়।
  আউটপুট বাংলায়। double-count নয় (manual subtotal auto-যোগ হয় না)।
- **অবস্থা:** C1, C2, C3, C7, register-driven excess, manual checks, evidence chips,
  FastAPI app, Excel report, KB — **সম্পন্ন**। C4/C5/C8 আংশিক/বাকি। §৭ দ্রষ্টব্য।

---

## ১. ব্যবহারকারী ও নীতি (কখনো লঙ্ঘন নয়)

- **নন-টেকনিক্যাল** বন্ড ও ভ্যাট নিরীক্ষায় **অভিজ্ঞ** ব্যবহারকারী। কারিগরি প্রশ্নের
  পরিণতি সহজ বাংলায় বোঝাতে হবে। **তাঁর ডোমেইন-সিদ্ধান্তই চূড়ান্ত।**
- সব **আউটপুট বাংলায়**, technical term ইংরেজিতে।
- **সততা > অতিরঞ্জন।** "প্রায় হয়ে গেছে" বলা নিষেধ — যা হয়েছে, ঠিক তা-ই বলুন;
  test fail করলে বলুন; skip করলে বলুন।
- **আইনি সংখ্যা (threshold, হার, মেয়াদ, SRO নম্বর) কখনো অনুমান/বানানো নয়।** gazette
  citation ছাড়া কোনো আইনি সীমা engine-এ বসানো যাবে না। অনিশ্চিত হলে ব্যবহারকারীকে জিজ্ঞাসা।
- **গোপনীয়তা:** প্রতিষ্ঠানের প্রকৃত ডেটা (entitlement xlsx, audit report docx) **git-এ
  commit নয়**, এই zip-এও নেই। শুধু কোড, KB (public gazette reference), synthetic sample।
- Certainty grading: **【V】** verified (gazette/দলিল দ্বারা প্রমাণিত) · **【E】** estimated ·
  **【P】** pending। KB ও finding-এ এই grade বজায় রাখুন।

---

## ২. ডোমেইন জ্ঞান — কাস্টমস বন্ড অডিটের মূল কাঠামো

### ২.১ বন্ডেড ওয়্যারহাউস কী
রপ্তানিমুখী প্রতিষ্ঠান শুল্ক-কর **স্থগিত** রেখে কাঁচামাল আমদানি করে বন্ডে রাখে, উৎপাদন
করে রপ্তানি করে। শর্ত লঙ্ঘন করলে স্থগিত শুল্ক-কর **দাবিযোগ্য (demand)** হয়। নিরীক্ষকের
কাজ = লঙ্ঘন খুঁজে দাবি নির্ধারণ।

### ২.২ প্রাপ্যতা (Entitlement / UP — Utilization Permission)
প্রতিটি HS কোডে কতটুকু কাঁচামাল শুল্কমুক্ত আমদানি করা যাবে তার সীমা। **প্রাপ্যতার ছক**
(entitlement schedule) থেকে আসে। বর্ধিত প্রাপ্যতা [বিধি ৮] থাকতে পারে।

### ২.৩ তফসিল-১ রেজিস্টার (Bond Register) — **সবচেয়ে গুরুত্বপূর্ণ**
প্রতিষ্ঠানের বন্ড রেজিস্টারে দুই ধরনের event:
- **into-bond** — কাঁচামাল বন্ডে প্রবেশ (আমদানি ছাড়)। **প্রবেশ নির্ভর করে into-bond
  রেজিস্টারের তারিখে।**
- **ex-bond** — কাঁচামাল বন্ড থেকে বের/ব্যবহার। **ব্যবহার নির্ভর করে ex-bond রেজিস্টারের
  তারিখে।**

> **⚠ FIFO নয়।** কাঁচামালের ব্যবহার FIFO স্টাইলে ধরা **ভুল**। প্রবেশ = into-bond তারিখ,
> ব্যবহার = ex-bond তারিখ — register-driven স্টক খতিয়ান। (ব্যবহারকারীর সুস্পষ্ট নির্দেশ;
> `assessment.allocate_excess_by_entry` এখন into_bond_date দিয়ে sort করে।)

### ২.৪ ছয়টি দাবি শ্রেণি (দাবি ১–৬)

| দাবি | বিষয় | সূত্র / যুক্তি | কোড |
|---|---|---|---|
| **দাবি ১** | অননুমোদিত HS কোড আমদানি | পূর্ণ BE (Bill of Entry) শুল্ক-কর | `_build_unauthorized` |
| **দাবি ২** | প্রাপ্যতার অতিরিক্ত আমদানি | register-driven আনুপাতিক assessment (+ cluster) | `_build_excess_and_utilization` + `assessment.assess_excess` |
| **দাবি ৩** | এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন | `min((প্রাপ্যতা+মজুত)÷৩, ধারণক্ষমতা)`; shield/ledger | `_check_bonding_capacity` + `capacity_ledger` |
| **দাবি ৪** | বিধি ১১(১) উৎপাদন ক্ষমতার ৮০% সীমা | aggregate কেজিতে যাচাই | `bonding_rules.check_capacity_limit` |
| **দাবি ৫** | **মেয়াদোত্তর (post-period) আমদানি** (C1) | অডিট মেয়াদের বাইরে into-bond | `_build_post_period` + `_is_post_period` |
| **দাবি ৬** | **মেয়াদোত্তীর্ণ কাঁচামাল / overstay** (C7) | মজুদকাল > সীমা → পৃথক দাবি | `_build_overstay` |

> **দ্বৈত গণনা রোধ:** manual check-এর subtotal কখনো grand total-এ **auto-যোগ হয় না**;
> শুধু নিরীক্ষক-**গৃহীত (accepted)** finding যোগ হয়। দাবি ১–৬ পৃথক, grand total = dynamic SUM।

### ২.৫ দুই-শাসন (dual-regime) temporal logic
- **কাস্টমস আইন ১৯৬৯** (পুরনো) vs **কাস্টমস আইন ২০২৩** — কার্যকর **০৬.০৬.২০২৪**।
- এককালীন ক্যাপাসিটি নতুন সূত্র **০১.০৭.২০২৬** থেকে শুধু ধারণক্ষমতা; মেয়াদ straddle করলে
  খণ্ডন। `bonding_rules.determine_regime` / `resolve_capacity` / `NEW_REGIME_DATE`।
- KB `13_KB_TEMPORAL_RESOLVER.md` তারিখ-ভিত্তিক আইন নির্বাচনের নিয়ম ধরে।

---

## ৩. আইনি ভিত্তি (মূল citation, certainty সহ)

| বিষয় | citation | grade |
|---|---|---|
| কাস্টমস আইন ২০২৩ | কার্যকর ০৬.০৬.২০২৪; ধারা ১১৯ (বন্ড), ধারা ৩২ (সুদ ১%/মাস ≤২৪ মাস) | 【V】 |
| বন্ড বিধিমালা পরিবার | SRO ২০৯–২১৪/২০২৪ | 【V】 |
| **Overstay / মজুদকাল** (দাবি ৬) | **SRO ২১১-আইন/২০২৪ বিধি ৩–৫ — সরাসরি/প্রচ্ছন্ন রপ্তানিমুখীতে সর্বোচ্চ ২৪ মাস**; গণনা-সূচনা: আমদানিতে ছাড়ের তারিখ | 【V】 |
| **মূল্য সংযোজন (T-06)** | SRO ২১২ বিধি ১০(৮): UP-তে VA হার ≥ ১৫%। **ভিত্তি = Input** (÷Input), FOB নয় — নিরীক্ষক-নির্ধারিত (Case-B নমুনায় ২৩.৪৫%) | 【V】 (ব্যবহারকারী-নিশ্চিত) |
| **VDS (উৎসে মূসক)** | মূসক ও সম্পূরক শুল্ক আইন ২০১২ ধারা ৪৯–৫০–৫৩, বিধি ৪০(১)(চ); **SRO ২৪০-আইন/২০২১/১৬৩-মূসক** | 【V】 (ব্যবহারকারী-নিশ্চিত) |
| TDS ≠ VDS ফাঁদ | "উৎসে কর কর্তন বিধিমালা ২০২৪" (SRO ১৬১-আইন/আয়কর) = **আয়কর** TDS, VDS নয় | 【V】 |
| রপ্তানি প্রত্যাবাসন (T-08) | ১২০ দিন | KB দ্রষ্টব্য |

> **সমাধিত KB-অভ্যন্তরীণ দুই বিরোধ (২০২৬-০৮-২৫):**
> (১) T-06 divisor — ব্যবহারকারী **÷Input** নির্ধারণ করেছেন; `schedule3_analyzer` +
> KB `07`/`08` সব ÷Input-এ সমন্বিত। (২) VDS SRO — **১৬৩-মূসক** নির্ধারিত; KB `04`/`08`/`13`
> থেকে ভুল "১৭৪" অপসারিত।

---

## ৪. স্থাপত্য (Architecture)

```
customs-bond-vat-copilot/
├── backend/                         ← canonical (Python)
│   ├── run_server.py                ← `python3 run_server.py` → :4800
│   ├── api/
│   │   ├── main.py                  ← FastAPI app + সব endpoint
│   │   └── static/{index.html,app.js,styles.css}  ← চালু UI (file view + ম্যানুয়াল যাচাই)
│   ├── services/
│   │   ├── import_analysis.py       ← ⭐ মূল engine, analyze() → ৬ দাবি
│   │   ├── assessment.py            ← assess_bill / assess_excess / allocate_excess_by_entry
│   │   ├── capacity_ledger.py       ← এককালীন ক্যাপাসিটি shield/ledger (register-driven)
│   │   ├── bonding_rules.py         ← regime নির্ণয়, ৮০% সীমা, straddle
│   │   ├── bond_register.py         ← তফসিল-১ into/ex-bond parsing
│   │   ├── schedule3_analyzer.py    ← T-01..T-08 আন্তঃকলাম যাচাই (T-06 ÷Input)
│   │   ├── report_writer.py         ← ১০+ শীট Excel (দাবি ১–৬ সহ)
│   │   ├── interest_penalty.py      ← ধারা ৩২ সুদ
│   │   ├── doc_requisition.py       ← ৫ শ্রেণির চাহিদাপত্র
│   │   └── checks/{numeric,validity,evidence}.py  ← manual check catalog
│   ├── knowledge/
│   │   ├── kb/                      ← ⭐ ১৫ মডিউল + 08_RULES_ENGINE.json
│   │   ├── kb_loader.py             ← KnowledgeBase("knowledge/kb").load()
│   │   ├── check_specs.py           ← NUMERIC_CHECKS / VALIDITY_CHECKS / BOND_LEGAL_REFS
│   │   └── {legal_scope,report_style,sro213_rmg,learned_rules}.py
│   ├── models/                      ← SQLAlchemy (company, entitlement, import_data, ...)
│   ├── ai/                          ← agent, matcher (৫-স্তর), unit_parser
│   ├── engines/excel_engine.py      ← Excel ইনজেশন
│   └── utils/bijoy*.py              ← Unicode ↔ SutonnyMJ (Bijoy) রূপান্তর
├── tests/                           ← ৭টি behavior test (নিচে §৬) + sample generator
├── public/ , src/                   ← পুরনো JS PWA (reference; canonical নয়)
├── MASTER_HANDOFF.md                ← এই ফাইল
├── VERIFICATION_v4.11.md , HANDOFF_v4.md   ← ঐতিহাসিক
└── README.md , INSTALL.md
```

**স্থাপত্য নীতি:** declarative check-spec (serializable spec + id-keyed compute fn)।
প্রস্তুত-তথ্য hot path-এ বয়ে নেওয়া (provider/model/channel/HS আগেই resolve)।

---

## ৫. Manual Check Catalog (`backend/services/checks/`)

- **numeric.py — ৯ numeric check** (দুই-তরফা: over/under):
  `num-entitlement`, `num-be-register-raw`, `num-be-register-machinery`,
  `num-be-register-sample`, `num-coefficient`, `num-ud-export`,
  `num-material-balance`, `num-wastage`, `num-overstay`।
  API: `run_numeric_checks(specs, inputs_by_check)` → `result_to_finding`।
- **validity.py — ৩ validity check:** `val-license-expiry`, `val-up-coverage`,
  `val-hs-entitlement`।
- **evidence.py — Smart Evidence Chip:** OCR টেক্সট → সংখ্যা extraction, দ্বিভাষিক synonym
  index + confidence + field suggestion। ASCII ও বাংলা digit উভয়।
- Spec উৎস: `backend/knowledge/check_specs.py`।

**API endpoints** (`api/main.py`): `/api/analyze/import`, `/api/analyze/import/xlsx`,
`/api/checks/specs`, `/api/checks/numeric`, `/api/checks/validity`,
`/api/checks/evidence/scan`।

---

## ৬. পরীক্ষা (Tests) — সবগুলো **PASS**

pytest নেই; প্রতিটি test plain script (assert + print)। চালান:
```bash
cd customs-bond-vat-copilot
for t in tests/test_*.py; do PYTHONPATH=backend python3 "$t"; done
```
| test | আওতা |
|---|---|
| `test_post_period_c1.py` | C1 — দাবি ৫ মেয়াদোত্তর আমদানি |
| `test_extended_entitlement_c2.py` | C2 — বর্ধিত প্রাপ্যতা + বিয়োজন যাচাই |
| `test_bond_license_capacity_c3.py` | C3 — বন্ড লাইসেন্স ক্যাপাসিটি অগ্রাধিকার |
| `test_register_driven_excess.py` | FIFO নয় — register-driven excess ordering |
| `test_manual_checks.py` | ৯ numeric + ৩ validity (২৯ assertion) |
| `test_evidence_chips.py` | evidence extraction (৮) |
| `test_overstay_c7.py` | C7 — দাবি ৬ overstay (৮) |

> নতুন behavior যোগ করলে **অবশ্যই** সংশ্লিষ্ট test যোগ/হালনাগাদ করুন, তারপরই commit।

---

## ৭. অবস্থা ম্যাট্রিক্স — **সম্পন্ন vs বাকি** (২০২৬-০৮-২৫)

| আইটেম | অবস্থা | প্রমাণ / টীকা |
|---|---|---|
| দাবি ১–৪ মূল engine | ✅ সম্পন্ন | `import_analysis.analyze()` |
| **C1** post-period (দাবি ৫) | ✅ সম্পন্ন | `_build_post_period` + test |
| **C2** বর্ধিত প্রাপ্যতা | ✅ সম্পন্ন | `effective_entitled_quantity`, `Rule8Observation` + test |
| **C3** বন্ড লাইসেন্স ক্যাপাসিটি | ✅ সম্পন্ন | `compute_warehouse_capacity(bond_license_capacity_mt=)` + test |
| register-driven excess (FIFO নয়) | ✅ সম্পন্ন | `allocate_excess_by_entry` + test |
| **C7** overstay (দাবি ৬) | ✅ সম্পন্ন | `_build_overstay`, SRO ২১১ ২৪ মাস 【V】 + test |
| manual checks (৯+৩) + evidence chips | ✅ সম্পন্ন | `checks/*` + test |
| FastAPI app + PWA UI | ✅ সম্পন্ন | `run_server.py`, `api/static/` |
| Excel report (দাবি ১–৬) | ✅ সম্পন্ন | `report_writer.py` |
| KB সংহতকরণ (১৫ মডিউল) | ✅ সম্পন্ন | `kb_loader` লোড করে |
| T-06 ÷Input, VDS ১৬৩ সংশোধন | ✅ সম্পন্ন | §৩ দ্রষ্টব্য |
| **C4** EPZ IP/EP পরিমাণ ক্রস-চেক | ⚠️ আংশিক | `doc_requisition`-এ শ্রেণি আছে; engine-এ পরিমাণ যাচাই নেই |
| **C5** বিদ্যুৎ-উৎপাদন সামঞ্জস্য | ❌ বাকি | প্রতি-কেজি বিদ্যুৎ-ব্যয় check নেই |
| **C8** পূর্ণ PRC/প্রত্যাবাসন | ⚠️ আংশিক | T-08 (১২০ দিন) আছে; পূর্ণ export-realization মডিউল নেই |
| KB citation → engine finding wire | ⬜ ঐচ্ছিক | finding-এ SRO/বিধি স্বয়ংক্রিয় সংযুক্তি |
| OCR স্তর (image → text) | ⬜ ঐচ্ছিক | evidence chip টেক্সট নেয়; OCR উৎস বাকি |

---

## ৮. কীভাবে চালাবেন (Run)

```bash
cd customs-bond-vat-copilot/backend
pip install -r requirements.txt        # প্রথমবার
python3 run_server.py                   # → http://localhost:4800
```
UI-তে: entitlement + imports + local purchase + register ফাইল আপলোড, প্যারামিটার
(next_entitlement_date, bond_license_capacity_mt, extension_applies, overstay_years,
overstay_as_of) দিয়ে **📥 বিশ্লেষণ**; অথবা **🧮 ম্যানুয়াল যাচাই** ভিউ।
`/api/analyze/import/xlsx` → দাবি ১–৬ সহ Excel।

KB যাচাই:
```python
from knowledge.kb_loader import KnowledgeBase
kb = KnowledgeBase("knowledge/kb"); kb.load()
```

---

## ৯. পরবর্তী AI-র জন্য কাজের ধারা

1. **নতুন কাজের আগে** এই ফাইল + `import_analysis.py` + সংশ্লিষ্ট `checks/*`/KB মডিউল পড়ুন।
2. **আইনি সংখ্যা** লাগলে KB-তে খুঁজুন; না পেলে ব্যবহারকারীকে জিজ্ঞাসা — **বানাবেন না**।
3. পরিবর্তনের সাথে **test** যোগ/হালনাগাদ, সব test চালিয়ে PASS নিশ্চিত করুন।
4. প্রতিষ্ঠানের প্রকৃত ডেটা **commit/zip নয়**। commit `--no-verify`; commit/PR টেক্সটে মডেল
   পরিচয় নয়।
5. সম্ভাব্য পরবর্তী target: **C4** (EPZ IP/EP পরিমাণ ক্রস-চেক), **C5** (বিদ্যুৎ-উৎপাদন),
   **C8** (পূর্ণ PRC), KB citation wire, OCR স্তর।

---

## ১০. Knowledge Base সূচি (`backend/knowledge/kb/`)

| ফাইল | বিষয় |
|---|---|
| `00_MASTER_INDEX.md` | KB সূচি ও ব্যবহারবিধি |
| `01_KB_CUSTOMS_ACT_2023.md` | কাস্টমস আইন ২০২৩ |
| `02_KB_BOND_RULES_SRO.md` | বন্ড বিধিমালা SRO |
| `03_KB_VAT_SD.md` | মূসক ও সম্পূরক শুল্ক |
| `04_KB_VDS_CA_AUDIT.md` | VDS + CA অডিট (SRO ১৬৩-মূসক) |
| `05_KB_EPZ_BEPZA.md` | EPZ / BEPZA |
| `06_KB_FX_TRADE_POLICY.md` | বৈদেশিক মুদ্রা / বাণিজ্য নীতি |
| `07_AUDIT_TEST_LIBRARY.md` | T-01..T-08 টেস্ট লাইব্রেরি (T-06 ÷Input) |
| `08_RULES_ENGINE.json` | মেশিন-পাঠ্য rules engine (constraint/trap) |
| `09_KB_BOND_SRO_2024_FULL.md` | বন্ড SRO ২০২৪ পূর্ণ |
| `10_KB_MUSHAK_FORMS.md` | মূসক ফরম |
| `11_KB_AUDIT_MANUAL.md` | অডিট ম্যানুয়াল |
| `12_KB_MUSHAK_FORM_FILLING_ERRORS.md` | মূসক ফরম পূরণ ভুল |
| `13_KB_TEMPORAL_RESOLVER.md` | তারিখ-ভিত্তিক আইন নির্বাচন |
| `14_KB_HISTORICAL_REGIME_1969.md` | ঐতিহাসিক ১৯৬৯ শাসন |
| `KB_PACKAGE_README.md` | KB প্যাকেজ পরিচিতি |

---

*এই প্যাকেজে প্রতিষ্ঠানের কোনো প্রকৃত (confidential) ডেটা নেই — শুধু কোড, public gazette
KB, এবং synthetic sample generator (`tests/make_*.py`)।*
