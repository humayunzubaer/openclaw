# মাস্টার অডিট প্ল্যাটফর্ম — AI Engine Knowledge Base
## Module 00: Master Index ও Operating Protocol
**Version:** 1.0 | **Build date:** 08-08-2026 | **Scope:** বাংলাদেশ কাস্টমস বন্ড অডিট (EPZ + non-EPZ) + CA Audit + উৎসে মূসক (VDS)

---

## ১. এই Knowledge Base-এর দর্শন (Design Philosophy)

এই KB একটি **verified scaffold** — সম্পূর্ণ আইন-পুস্তকের প্রতিলিপি নয়। AI Engine-এর কাজ হবে এই scaffold থেকে সঠিক আইনি node শনাক্ত করা, test চালানো, এবং finding উৎপাদন করা। প্রতিটি আইনি দাবির সাথে certainty grade যুক্ত থাকবে; engine কখনো grade-বিহীন citation ব্যবহার করবে না।

**তিন দৃষ্টিকোণ (Three-Perspective Annotation):** প্রতিটি গুরুত্বপূর্ণ আইনি node তিনভাবে ব্যাখ্যাত:
- **[লার্নার]** — সরল বাংলায় বিধানটির বাস্তব অর্থ কী
- **[কর্মকর্তা]** — NBR-এর অভিজ্ঞ কর্মকর্তা হিসেবে অডিটে কীভাবে প্রয়োগ হবে, কোন document চেক করতে হবে
- **[বিচারক]** — adjudication/আপিলে টিকতে হলে কী প্রমাণ লাগবে, কোথায় দুর্বলতা

## ২. Certainty Grading Protocol (বাধ্যতামূলক)

| Grade | চিহ্ন | অর্থ | Engine-এর আচরণ |
|---|---|---|---|
| Verified | 【V】 | প্রাথমিক উৎস (bdlaws.minlaw.gov.bd, NBR gazette, প্রতিষ্ঠিত অডিট-চর্চা) থেকে যাচাইকৃত | SCN/আনুষ্ঠানিক finding-এ ব্যবহারযোগ্য |
| Estimated | 【E】 | নির্ভরযোগ্য secondary source বা পূর্ব-অডিট চর্চা থেকে; ধারা/বিধি নম্বর সম্ভাব্য সঠিক | Draft-এ ব্যবহারযোগ্য; SCN-এর আগে gazette-এ যাচাই বাধ্যতামূলক |
| Pending | 【P】 | নির্দিষ্ট সংখ্যা/তারিখ/হার অযাচাইকৃত | ফাঁকা রাখুন বা "যাচাই করুন" flag দিন; **কখনো অনুমানে পূরণ নয়** |

**Engine hard rules:**
1. কোনো ধারা, বিধি, SRO নম্বর, হার বা তারিখ **কখনো fabricate করা যাবে না**। KB-তে না থাকলে output-এ `[যাচাই করুন]` (লাল, C00000) লিখতে হবে।
2. প্রতিটি finding-এর micro-structure: **identify → quantify → cite law → state consequence**।
3. বড় অঙ্ক **অঙ্কে + কথায়** দ্বৈত-উল্লেখ (যেমন: ৳৩,৭৫,০০,০০০/- (তিন কোটি পঁচাত্তর লক্ষ টাকা)); লাখ/কোটি format।
4. আক্রমণাত্মক নয় — **adjudication-proof** দাবি; আইনগতভাবে দুর্বল finding চিহ্নিত করে বাদ দেওয়ার সুপারিশ করা engine-এর দায়িত্ব।
5. Output ভাষা: বাংলা (আনুষ্ঠানিক দলিল-রীতি); English technical terms ইংরেজিতেই (B/E, HS Code, CD, RD, SD, VAT, AIT, AT, Assessable Value, LC, PRC, FOB, coefficient)। Human-facing DOCX-এ বাংলা = SutonnyMJ (Bijoy ANSI encoding), English = Times New Roman; findings লাল (C00000) ব্যতীত কোনো রং নয়; Legal size (8.5″×14″) formal report।

## ৩. Module Map

| Module | ফাইল | বিষয়বস্তু |
|---|---|---|
| 01 | 01_KB_CUSTOMS_ACT_2023.md | কাস্টমস আইন ২০২৩ — সংজ্ঞা, ওয়্যারহাউসিং অধ্যায় (ধারা ১০৮–১৩৩), শুল্কায়ন, PCA, দণ্ড-তামাদি |
| 02 | 02_KB_BOND_RULES_SRO.md | ওয়্যারহাউস লাইসেন্সিং বিধিমালা ২০২৪ (SRO 209), General Bond Rules, UP/UD, সংশোধনী |
| 03 | 03_KB_VAT_SD.md | মূসক ও এসডি আইন ২০১২ + বিধিমালা ২০১৬, Mushak forms, Finance Act 2024→2026 timeline |
| 04 | 04_KB_VDS_CA_AUDIT.md | **অতিরিক্ত scope:** উৎসে মূসক (ধারা ৪৯, VDS বিধিমালা ২০২১) + CA Audit যাচাই module |
| 05 | 05_KB_EPZ_BEPZA.md | EPZ Customs Rules 1984, BEPZA কাঠামো, DTA sale, sub-contract |
| 06 | 06_KB_FX_TRADE_POLICY.md | FERA 1947, GFET, BTB LC, রপ্তানি মূল্য প্রত্যাবাসন, EDF/EFPF, IPO/EPO 2024-27 |
| 07 | 07_AUDIT_TEST_LIBRARY.md | Calculation engine: ১৩টি core test — সূত্র, threshold, finding template |
| 08 | 08_RULES_ENGINE.json | Machine-readable rule definitions (id, inputs, formula, law_ref, certainty, severity) |
| **09** | 09_KB_BOND_SRO_2024_FULL.md | **বন্ড SRO-পরিবার ২০৯–২১৪/২০২৪-এর গেজেট-পাঠ:** সকল বিধি + তফসিল/ছক কলাম-স্তরে (১৬-কলাম বন্ড রেজিস্ট্রার, UP-ফরম্যাট, বার্ষিক বিবরণী ছক-ক/খ, তফসিল ৪-৫) — Module 02-এর authoritative সম্প্রসারণ 【V】 |
| **10** | 10_KB_MUSHAK_FORMS.md | **মূসক ফরম ঘর-স্তরে:** ৯.১-এর ১১ অংশ-৬৩ নোট-৭ সাবফর্ম-যোগফল-সূত্র (অফিসিয়াল ফরম-পাঠ 【V】) + ৬.৩/৬.৬/৬.১-৬.২/৪.৩/৬.১০ + test-ম্যাপিং |
| **11** | 11_KB_AUDIT_MANUAL.md | নিরীক্ষা-ম্যানুয়াল স্তর: বিধিবদ্ধ বার্ষিক-নিরীক্ষা কাঠামো (৬০+৯০ দিন; ২১২-বিধি ১৩-সূচিপত্র), ধারা ৯৯-১০০, CBC Management Book/2017 রেজিস্ট্রি, পোর্টাল-অবকাঠামো, ৮-ধাপ কার্যপ্রবাহ |
| **14** | 14_KB_HISTORICAL_REGIME_1969.md | **ঐতিহাসিক রেজিম (Customs Act 1969):** একাদশ অধ্যায় ৮৪–১১৯B ধারা-মানচিত্র + সংশোধনী-নোঙর, ধারা ৩০-এর তিন-যুগ হার-তারিখ সারণি, ধারা ৩২ তামাদি-স্তর, ২০২৩↔১৯৬৯ test-অভিযোজন সারণি 【V】 |
| **13** | 13_KB_TEMPORAL_RESOLVER.md | **কাল-নির্ণয় স্তর:** substantive/procedural দ্বৈত-সূত্র (ধারা ২৬৯ হেফাজত), ঘটনা-নোঙর সারণি, কার্যকরতা-timeline registry, ৬-ধাপ resolve-অ্যালগরিদম, তামাদি-স্তর (২০৪(১)/৩৩(৪)), ১০টি কাল-ফাঁদ |
| **12** | 12_KB_MUSHAK_FORM_FILLING_ERRORS.md | **মূসক ফরম পূরণ ও ত্রুটি-শনাক্ত ম্যানুয়াল:** বিধিমালা ২০১৬-র ছক-স্তর — ৬.১ (২১ কলাম), ৬.২ (২১), ৬.২.১ (২৬), ৬.৩ (বিধি ৪০(১)(গ)-তালিকা+১০ কলাম), ৬.৪–৬.১০, ৪.৩, ২-সিরিজ, ৭.১; প্রতি-ফরম ত্রুটি-চেকলিস্ট + আন্তঃছক ম্যাট্রিক্স; মাস্টার-ক্লজ বিধি ৪০(৩) |

## ৪. ভাষাগত সূক্ষ্মতা (Linguistic Precision Layer)

Adjudication-এ শব্দচয়নই মামলা জেতায়/হারায়। Engine নিচের পার্থক্য কঠোরভাবে মানবে:

| শব্দ | আইনি অর্থ | ভুল-প্রয়োগ ঝুঁকি |
|---|---|---|
| **ন্যস্ত করা** (place under) | পণ্যকে কোনো কাস্টমস পদ্ধতির অধীনে আনা (কাস্টমস আইন ২০২৩, ধারা ২(১৯)) 【V】 | "জমা রাখা"-র সাথে গুলিয়ে ফেলা |
| **ছাড় (release)** | ধারা ৯২ মোতাবেক শর্তপূরণ-পরবর্তী release 【V】 | "খালাস"-এর সমার্থক নয় সব ক্ষেত্রে |
| **খালাস (clearance)** | দেশীয় ভোগ/রপ্তানির জন্য ex-bond clearance (ধারা ১১৮, ১৩৪) 【V】 | ex-bond B/E ছাড়া "খালাস" দাবি অগ্রহণযোগ্য |
| **অপসারণ (removal)** | ওয়্যারহাউস থেকে সরানো; অননুমোদিত হলে ধারা ১২৬(ক) demand 【V】 | চুরি/ঘাটতির সাথে সমীকরণ না করা |
| **সরকারের নিকট হস্তান্তরিত বলিয়া গণ্য** | ৩০/২১ দিনে ছাড় না হলে deemed transfer (ধারা ৯৪) 【V】 | বাজেয়াপ্তি (confiscation) নয় |
| **ন্যায়নির্ণয়ন (adjudication)** | জরিমানাযোগ্য অপরাধে প্রশাসনিক কার্যক্রম (ধারা ২(২৯)) 【V】 | ফৌজদারি মামলার সাথে মিশ্রণ নয় |
| **প্রত্যর্পণ (drawback)** | ধারা ৩৬–৪০ 【V】 | refund (ধারা ৩৪, ৩ বছর তামাদি) থেকে ভিন্ন |
| **অপচয়/বর্জ্য (wastage/waste)** | ধারা ১১৭(২): রপ্তানি হলে শুল্কমুক্ত (ধ্বংস সাপেক্ষে), দেশীয় ভোগে শুল্কযোগ্য 【V】 | অনুমোদিত% এর বাইরের ঘাটতি ≠ স্বাভাবিক অপচয় |
| **গণ্য রপ্তানিকারক (deemed exporter)** | সরাসরি রপ্তানি নয়; local BTB LC-তে বৈদেশিক মুদ্রায় মূল্যপ্রাপ্ত 【V】 | zero-rating দাবির শর্ত ভিন্নভাবে যাচাই্য |

## ৫. Engine Retrieval Protocol (RAG guideline)

1. **Query classification:** প্রশ্ন/দলিল কোন module-এ পড়ে চিহ্নিত করুন (multi-module সম্ভব, যেমন DTA sale = 01+05+07)।
2. **Node retrieval:** সংশ্লিষ্ট ধারা/বিধি node + তার তিন-দৃষ্টিকোণ annotation + linkage আনুন।
3. **Test execution:** Module 07/08-এর সংশ্লিষ্ট test-এ ডেটা বসান; সূত্র formula-driven (hardcoded total নিষিদ্ধ)।
4. **Certainty resolution:** Output-এর প্রতিটি citation-এ grade বহন করুন; 【P】থাকলে "প্রাথমিক উৎস যাচাই সাপেক্ষে" শর্ত যুক্ত করুন।
5. **Finding assembly:** identify→quantify→cite→consequence; বিকল্প ব্যাখ্যা থাকলে defensibility নোট দিন।
6. **Update hook:** নতুন SRO/অর্থ আইন পেলে সংশ্লিষ্ট node-এ `amended_by` entry যোগ করুন — পুরোনো text মুছবেন না (temporal versioning; অডিট period অনুযায়ী প্রযোজ্য version বাছাই)।

## ৬. Temporal Applicability Rule (অত্যন্ত গুরুত্বপূর্ণ)

অডিট period-এর তারিখ অনুযায়ী প্রযোজ্য আইন-সংস্করণ নির্বাচন করতে হবে:
- **০৬-০৬-২০২৪-এর পূর্বের ঘটনা:** Customs Act 1969 (ধারা ৮৪–১১৯, Chapter XI) প্রযোজ্য 【V】
- **০৬-০৬-২০২৪ থেকে:** কাস্টমস আইন ২০২৩ কার্যকর — SRO নং ১৫৩-আইন/২০২৪, তারিখ ২৮-০৫-২০২৪ 【V — bdlaws】
- **ভ্যাট return cadence:** জুন ২০২৬ পর্যন্ত মাসিক Mushak 9.1; অর্থ আইন ২০২৬ (Act 96 of 2026, কার্যকর ০১-০৭-২০২৬) থেকে ৩ কর-মেয়াদ চক্রে return, চক্র-শেষের ১৫ দিনের মধ্যে দাখিল 【V — KPMG/Bloomberg Tax; gazette cross-check করুন】

## ৭. Source Registry (প্রাথমিক উৎস)

1. bdlaws.minlaw.gov.bd — Act 1476 (কাস্টমস আইন ২০২৩), Act 1106 (মূসক ও এসডি আইন ২০১২)
2. nbr.gov.bd → regulations (Customs Rules, VAT Rules, SRO archive)
3. hub.bangladeshcustoms.gov.bd/resource/legislations — Bonded Warehouse Licensing Rules 2024, General Bond Rules 2024, Customs Act 2023 Effectiveness Gazette
4. bb.org.bd — GFET + FE circulars; exp.bb.org.bd (session-ভিত্তিক; সরাসরি fetch অসম্ভব — ব্যবহারকারীকে export/PDF নিতে বলুন)
5. bepza.gov.bd — Customs (EPZ) Rules 1984, নির্দেশিকা
6. mincom.gov.bd — Import/Export Policy Order
