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
  modules/                        অডিট-টাইপ সংজ্ঞা (checklist, doc types, legal map)
  report/generate.js              Working Paper / Note Sheet / Final Report
public/                           UI (ড্যাশবোর্ড, নথি, findings, রিপোর্ট)
audits/                           প্রতিটি অডিটের কেস-ফোল্ডার (git-ignored)
```

## রিইউজ কীভাবে কাজ করে

প্রতিটি অডিট একটি স্বয়ংসম্পূর্ণ ফোল্ডার। একই ধরনের প্রতিষ্ঠানের পরবর্তী নিরীক্ষায় — মডিউলের checklist, আইন-ম্যাপিং ও রিপোর্ট-টেমপ্লেট আগে থেকেই প্রস্তুত থাকে, তাই শুধু নতুন নথি যোগ করলেই বেশিরভাগ কাজ পুনঃব্যবহৃত হয়।

---

## রোডম্যাপ

- **Phase 1 (এই সংস্করণ):** নথি + OCR হুক + checklist খসড়া + Working Paper/Note Sheet/Final Report + ড্যাশবোর্ড। ✅
- **Phase 2:** নলেজ বেস RAG + সত্যিকার AI বিশ্লেষণ (ollama/claude) + Evidence-এ পৃষ্ঠা-লেভেল লিংক।
- **Phase 3:** বাকি ৪টি মডিউল (প্রচ্ছন্ন, পোশাক, VAT limited, VAT proprietorship)।
- **Phase 4:** টেমপ্লেট লাইব্রেরি + আগের অডিট থেকে "clone"।

> ⚠️ আইনি রেফারেন্স (`knowledge/`) সম্পাদনাযোগ্য ডিফল্ট — প্রতিটি অডিটে নিরীক্ষক বর্তমান SRO/বিধি যাচাই করে নেবেন। টুলটি খসড়া দ্রুততর করে, চূড়ান্ত পেশাগত রায় দেয় না।
