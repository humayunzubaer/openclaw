# Customs Bond & VAT Audit Copilot

কাস্টমস **বন্ড অডিট** ও **ভ্যাট অডিট**-এর জন্য একটি লোকাল, অফলাইন-ফার্স্ট বিশেষায়িত ওয়ার্কবেঞ্চ। সাধারণ চ্যাটবট নয় — নথি ব্যবস্থাপনা, OCR, checklist-ভিত্তিক বিশ্লেষণ, আইনভিত্তিক নলেজ বেস, Working Paper, Note Sheet, চূড়ান্ত রিপোর্ট ও Evidence ব্যবস্থাপনা একসাথে।

রিপোর্ট বাংলায়, technical term ইংরেজিতে।

---

## দ্রুত শুরু

```bash
cd customs-bond-vat-copilot
node src/server.js
```

ব্রাউজারে খুলুন: **http://localhost:4700**

> কোর অ্যাপ চালাতে কোনো `npm install` লাগে না — শুধু Node.js 22.19+। সব ডেটা আপনার কম্পিউটারেই থাকে, ইন্টারনেটে যায় না।

### OCR চালু করা (ঐচ্ছিক)

স্ক্যান করা নথি থেকে টেক্সট বের করতে:

```bash
npm install tesseract.js
```

তারপর সার্ভার রিস্টার্ট করুন। প্রথমবার বাংলা (`ben`) + ইংরেজি (`eng`) ভাষা-ডেটা একবার নামে; পরে অফলাইনে চলে।

### AI বিশ্লেষণ (ঐচ্ছিক, pluggable)

- **none** (ডিফল্ট) — নিয়ম-ভিত্তিক খসড়া, ১০০% অফলাইন।
- **ollama** — লোকাল মডেল (ডেটা কম্পিউটার ছাড়ে না)। *[পরবর্তী ধাপে]*
- **claude** — Claude API (নির্ভুল; OCR টেক্সট ইন্টারনেটে যায়)। *[পরবর্তী ধাপে]*

---

## অডিটের ধরন

| ধরন | মডিউল | অবস্থা |
|-----|-------|--------|
| বন্ড — সরাসরি (পোশাক শিল্প ব্যতীত) | `bond-direct-non-garments` | ✅ সক্রিয় |
| বন্ড — প্রচ্ছন্ন রপ্তানি | `bond-deemed-export` | 🕒 পরিকল্পিত |
| বন্ড — সরাসরি (পোশাক শিল্প) | `bond-direct-garments` | 🕒 পরিকল্পিত |
| ভ্যাট — লিমিটেড কোম্পানি | `vat-limited` | 🕒 পরিকল্পিত |
| ভ্যাট — প্রোপ্রাইটরশিপ | `vat-proprietorship` | 🕒 পরিকল্পিত |

নতুন মডিউল = `src/modules/`-এ একটি ফাইল + `src/modules/index.js`-এ register।

---

## কাঠামো

```
src/
  server.js                       লোকাল সার্ভার (zero-dependency)
  storage.js                      অডিট = ফোল্ডার (JSON + নথি), পোর্টেবল
  ocr.js                          Tesseract wrapper (lazy, optional)
  ai/index.js                     pluggable AI provider (none / ollama / claude)
  settings.js                     লোকাল সেটিংস (provider পছন্দ, API key)
  report/export.js                Word / Excel / PDF export (zero-dependency)
  knowledge/bond-legal.js         আইন/বিধি নলেজ বেস
  modules/                        অডিট-টাইপ সংজ্ঞা (checklist, doc types, numeric specs, legal map)
  checks/numeric.js               সংখ্যাগত auto-check ইঞ্জিন (reconciliation + রাজস্ব হিসাব)
  checks/evidence.js              Smart Evidence Chip extraction (OCR → context-aware সংখ্যা)
  report/generate.js              Working Paper / Note Sheet / Final Report
public/                           UI (ড্যাশবোর্ড, নথি, findings, সংখ্যাগত যাচাই, রিপোর্ট)
audits/                           প্রতিটি অডিটের কেস-ফোল্ডার (git-ignored)
test/                             node:test (শূন্য-নির্ভরতা) — চালান: node --test
```

## সংখ্যাগত যাচাই (Auto-check)

"🧮 সংখ্যাগত যাচাই" ট্যাবে নিরীক্ষক সংখ্যা বসালে টুল স্বয়ংক্রিয়ভাবে ঘাটতি ও সম্ভাব্য রাজস্ব হিসাব করে। বন্ড (non-garments) মডিউলে এখন ৯টি check:

| Check | কী হিসাব হয় | আইন |
|-------|-------------|-----|
| Entitlement অতিক্রম | আমদানি − অনুমোদিত entitlement; অতিরিক্ত × শুল্ক-কর | BWL Rules |
| B/E vs রেজিস্টার — **কাঁচামাল** | কাঁচামাল B/E আমদানি − ইন-টু-বন্ড রেজিস্টার | BWL Rules |
| B/E vs রেজিস্টার — **মেশিনারিজ** | মেশিনারিজ B/E আমদানি − মূলধনী/মেশিনারিজ রেজিস্টার | BWL Rules |
| B/E vs রেজিস্টার — **Sample** | Sample B/E আমদানি − Sample রেজিস্টার | BWL Rules |
| Coefficient অতিরিক্ত ব্যবহার | প্রকৃত ব্যবহার − (উৎপাদন × coefficient) | BWL Rules |
| UD/EP vs রপ্তানি | দাবিকৃত ব্যবহার − রপ্তানি-সমর্থিত ব্যবহার (ইপিজেড হলে UP/UD-এর বদলে **EP/Sales Contract**) | Customs Act §21 |
| কাঁচামাল Reconciliation | (Opening+Import) − (রপ্তানি-ব্যবহার + অপচয় + Closing) = অহিসাবকৃত | Customs Act §156 |
| অপচয় (Wastage) | দাবিকৃত − (ব্যবহৃত × অনুমোদিত হার%) | BWL Rules |
| Overstay | মেয়াদোত্তীর্ণ পরিমাণ × শুল্ক-কর | BWL Rules |

- শুল্ক-কর/একক ঐচ্ছিক — না দিলে শুধু পরিমাণ-ব্যত্যয় দেখায়, রাজস্ব ০।
- flag হওয়া result "➕ Finding" চেপে চূড়ান্ত রিপোর্টে নেওয়া যায় (ডুপ্লিকেট বাদ)। **দ্বৈত গণনা এড়াতে** সংখ্যাগত উপমোট নিজে থেকে চূড়ান্ত রাজস্ব-মোটে যোগ হয় না — শুধু গৃহীত Finding-ই যোগ হয়।
- সব হিসাব সার্ভারে (`src/checks/numeric.js`), তাই testable ও রিপোর্টে (Word/Excel/PDF) অন্তর্ভুক্ত।

## Smart Evidence Chip (OCR → সংখ্যা)

"🧮 সংখ্যাগত যাচাই" ট্যাবে **🔍 নথি থেকে Evidence** চাপলে OCR-করা নথি থেকে সংখ্যা তোলা হয়। generic number নয় — প্রতিটি **Evidence Chip** ধরে রাখে:

- **document** (কোন নথি) ও **page** (পৃষ্ঠা, form-feed দিয়ে সনাক্ত)
- **source text** — সংখ্যার আশপাশের OCR স্নিপেট (কোথা থেকে এলো)
- **field suggestion** — context-aware: keyword (label + check-title + synonym) মিলিয়ে কোন check-এর কোন input-এ বসবে (যেমন "মেশিনারিজ রেজিস্টার" → মেশিনারিজ check-এর registerQty)
- **confidence score** — token-মান + field-match + unit/currency cue মিলিয়ে ০–১

নিরীক্ষক সঠিক field বেছে **প্রয়োগ** চাপলে মানটি field-এ বসে, numeric পুনঃহিসাব হয়, এবং **audit trail** (`evidence.json`) লেখা হয় — কোন মান, কোন নথির কোন পৃষ্ঠা থেকে, কোন confidence-এ, কে, কখন প্রয়োগ করলেন (override হলে আগের মানসহ)। **🧾 Trail** বাটনে পুরো log দেখা যায়। field-এ provenance badge (📄 নথি · পৃ.N · %) দেখায় মানটি কোথা থেকে এলো; হাতে বদলালে badge স্বয়ংক্রিয়ভাবে সরে যায় (log অক্ষত থাকে)।

> extraction ইঞ্জিন `src/checks/evidence.js`; OCR চালু (`npm install tesseract.js`) থাকলে নথির টেক্সট থেকেই সংখ্যা আসে। auto-map নয় — টুল সাজেশন দেয়, চূড়ান্ত সিদ্ধান্ত নিরীক্ষকের।

## Evidence ↔ Finding (পৃষ্ঠা-লেভেল প্রমাণ)

প্রতিটি Finding তার সমর্থনকারী প্রমাণ (নথি + পৃষ্ঠা + source) ধরে রাখে:

- **স্বয়ংক্রিয়:** numeric check থেকে Finding-এ নিলে, যে input-গুলো evidence chip দিয়ে ভরা হয়েছিল সেই নথির পৃষ্ঠাগুলো Finding-এ নিজে থেকেই যুক্ত হয় — অর্থাৎ সংখ্যাগত finding তার উৎস নথি/পৃষ্ঠা নিজেই cite করে।
- **ম্যানুয়াল:** Finding এডিটরে "Evidence — নথি + পৃষ্ঠা" সেকশনে নথি বেছে, পৃষ্ঠা ও (ঐচ্ছিক) source টেক্সট দিয়ে যুক্ত/বাদ দেওয়া যায়।
- **রিপোর্টে:** Working Paper, Final Report, Word ও Excel — সবখানে Evidence কলামে "নথি (পৃ.N)" citation আসে।

## রিইউজ কীভাবে কাজ করে

প্রতিটি অডিট একটি স্বয়ংসম্পূর্ণ ফোল্ডার। একই ধরনের প্রতিষ্ঠানের পরবর্তী নিরীক্ষায় — মডিউলের checklist, আইন-ম্যাপিং ও রিপোর্ট-টেমপ্লেট আগে থেকেই প্রস্তুত থাকে, তাই শুধু নতুন নথি যোগ করলেই বেশিরভাগ কাজ পুনঃব্যবহৃত হয়।

---

## রোডম্যাপ

- **Phase 1 (এই সংস্করণ):** নথি + OCR হুক + checklist খসড়া + সংখ্যাগত auto-check + Working Paper/Note Sheet/Final Report + ড্যাশবোর্ড। ✅
- **Phase 2:** নলেজ বেস RAG + সত্যিকার AI বিশ্লেষণ (ollama/claude) + Evidence-এ পৃষ্ঠা-লেভেল লিংক + OCR টেক্সট থেকে সংখ্যা auto-extract।
- **Phase 3:** বাকি ৪টি মডিউল (প্রচ্ছন্ন, পোশাক, VAT limited, VAT proprietorship)।
- **Phase 4:** টেমপ্লেট লাইব্রেরি + আগের অডিট থেকে "clone"।

> ⚠️ আইনি রেফারেন্স (`knowledge/`) সম্পাদনাযোগ্য ডিফল্ট — প্রতিটি অডিটে নিরীক্ষক বর্তমান SRO/বিধি যাচাই করে নেবেন। টুলটি খসড়া দ্রুততর করে, চূড়ান্ত পেশাগত রায় দেয় না।
