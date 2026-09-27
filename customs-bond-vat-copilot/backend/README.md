# Backend — Customs Bond Audit Intelligence Platform (Python)

Module 1 (Import Intelligence) engine + FastAPI সার্ভার + লোকাল UI। একই process-এ
engine ও UI — শুধু একটি কমান্ডে চলে, সম্পূর্ণ অফলাইন।

## চালানো

```bash
cd customs-bond-vat-copilot/backend
python3 -m pip install -r requirements.txt      # একবারই (ইন্টারনেট লাগে)
python3 run_server.py
```

ব্রাউজারে: **http://localhost:4800**
একই Wi-Fi/LAN-এ ফোন হইতে: `http://<এই-কম্পিউটারের-IP>:4800`

> ন্যূনতম নির্ভরতা (engine + API চালাতে): `fastapi uvicorn python-multipart pandas numpy openpyxl`।
> বাকি ভারী প্যাকেজ (faiss, sentence-transformers, easyocr) কেবল Level-2 AI/OCR স্তরের জন্য —
> Module 1 চালাতে লাগে না।

## যা করা যায় (Module 1)

UI-তে **প্রাপ্যতা শীট** ও **আমদানি (AIS/MIS/IM-4)** আপলোড করে "বিশ্লেষণ" চাপলে —
৫টি দাবিসহ সারসংক্ষেপ, সতর্কতা ও বিস্তারিত টেবিল দেখা যায়; "Excel কার্যপত্র" চাপলে
১০-শীট `.xlsx` নামে।

| দাবি | বিষয় |
|---|---|
| ১ | অননুমোদিত এইচএস কোড — পূর্ণ BE শুল্ক-কর |
| ২ | প্রাপ্যতার অতিরিক্ত — FIFO আনুপাতিক |
| ৩ | এককালীন বন্ডিং ক্যাপাসিটি লঙ্ঘন (shield/ledger) |
| ৪ | বিধি ১১(১) উৎপাদন ক্ষমতার ৮০% সীমা |
| ৫ | মেয়াদ সমাপনান্তে প্রাপ্যতা ব্যতীত আমদানি |

ঐচ্ছিক প্যারামিটার: নতুন প্রাপ্যতা তারিখ (মেয়াদোত্তর দাবির সীমা), বন্ড লাইসেন্স/
ওয়্যারহাউস ধারণক্ষমতা (মে.টন)।

## API

| Method | Path | কাজ |
|---|---|---|
| GET | `/api/health` | সার্ভার যাচাই |
| POST | `/api/analyze/import` | প্রাপ্যতা+আমদানি → ফলাফল JSON |
| POST | `/api/analyze/import/xlsx` | একই → ১০-শীট Excel ডাউনলোড |
| GET | `/` | লোকাল UI |

আপলোড: multipart — `entitlement_file`, `imports_file` (আবশ্যক), `local_file` (ঐচ্ছিক);
form: `next_entitlement_date` (YYYY-MM-DD), `bond_license_capacity_mt`,
`warehouse_capacity_mt`।

## সীমাবদ্ধতা (বর্তমান)

- **দাবি ৩ (বন্ডিং ক্যাপাসিটি)** পূর্ণ যাচাই কনজাম্পশন রেজিস্টার (তফসিল-১) সাপেক্ষ —
  না থাকিলে "যাচাই স্থগিত" দেখায় (নিরীক্ষা-নীতি অনুযায়ী)।
- Excel কার্যপত্রে এখনো **দাবি ৫**-এর পৃথক শীট নেই (JSON/UI-তে আছে) — পরবর্তী কাজ।
- OCR, Local AI (Level-2), Module 2–6 এখনো যুক্ত হয়নি।
