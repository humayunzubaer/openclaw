# Personal Scanner — অফলাইন বাংলা OCR

পুরোপুরি অফলাইন (ফোনের ভেতরেই চলে) বাংলা ও ইংরেজি ডকুমেন্ট স্ক্যানার। এই ফোল্ডারে আছে এর **OCR ইঞ্জিন**
(C++; OpenCV + Tesseract) আর নির্ভুলতা মাপার **benchmark**। মোবাইল অ্যাপ (Flutter) পরের ধাপে এই একই
ইঞ্জিন ব্যবহার করবে, তাই এখানে মাপা ফলই ফোনে পাওয়া যাবে।

## ইঞ্জিন কী কী করে

| ধাপ | কাজ |
|---|---|
| পাতা খোঁজা | ছবিতে কাগজের চার কোণা খুঁজে বাঁকা পাতা সোজা করে |
| আলো সমান করা | ছায়া, ঝলক আর অসমান আলো দূর করে কাগজকে সাদা করে |
| দিক ঠিক করা | পাশ ফেরানো (৯০°) বা উল্টো (১৮০°) পাতা নিজে থেকে সোজা করে |
| ভাষা বাছাই | পাতাটা বাংলা না ইংরেজি, নিজেই বুঝে সঠিক মডেল বেছে নেয় |
| হেলানো ঠিক করা | সামান্য হেলে থাকা লেখা সোজা করে |
| মাপ ঠিক করা | লেখা মডেলের পছন্দের আকারে আনে |
| টেবিল | ছকের দাগ চিনে মুছে দেয়, প্রতিটা ঘর আলাদা করে পড়ে (Excel-এ ঘর ধরে রপ্তানির জন্য) |
| সংখ্যা যাচাই | সংখ্যার মতো শব্দ শুধু-অঙ্ক মোডে বাংলা ও ইংরেজি দুইভাবে আবার পড়ে, বেশি নিশ্চিতটা রাখে |
| কলাম যুক্তি | যে কলামে বেশিরভাগ সংখ্যা, সেখানে "ঙ"-কে "৬" হিসেবে ঠিক করে |
| ইংরেজি উদ্ধার | বাংলা পাতায় "LC No.", "Invoice" ইত্যাদি ইংরেজি শব্দ ইংরেজি মডেলে আবার পড়ে |

## নির্ভুলতা (benchmark)

৫৪টা কৃত্রিম কাগজ (ফর্ম, টেবিল, চিঠি; ৬টা বাংলা ফন্ট; পরিষ্কার / স্ক্যানার / মোবাইল ছবি):

| | অক্ষর | শব্দ | সংখ্যা |
|---|---|---|---|
| সাধারণ Tesseract | ৬৫% | ৫৯% | ৫৯% |
| **Personal Scanner** | **৯৮%** | **৯৫%** | **৯৬%** |

শুধু টেবিল: সংখ্যা ৬% → ৯৫%+। মোবাইলে তোলা ছবি: অক্ষর ~৬০% → ~৯৮%।
Manus-এর ৩টা নমুনা ছবি: অক্ষর ৫৭% → ৯৫%, সংখ্যা ৬৭% → ১০০%।

> এগুলো কৃত্রিম কাগজে মাপা। আসল কাগজের ফল আলাদা হবে; আসল নমুনা দিয়ে আলাদা পরীক্ষা
> `bench/private/`-এ (git-এ যায় না) চালানো হয়।

## চালানো

```bash
# Ubuntu/Debian
sudo apt-get install cmake g++ libopencv-{core,imgproc,imgcodecs}-dev libtesseract-dev \
  tesseract-ocr-ben tesseract-ocr-eng libraqm0 fonts-noto-core fonts-lohit-beng-bengali \
  fonts-beng-extra fonts-freefont-ttf
pip install -r bench/requirements.txt

cmake -S . -B build && cmake --build build -j
./build/ps_ocr ছবি.jpg            # লেখা (টেবিলের ঘর tab দিয়ে আলাদা)
./build/ps_ocr --json ছবি.jpg     # ঘর, অবস্থান ও নিশ্চয়তাসহ JSON
./build/ps_ocr --debug out/ ছবি.jpg   # প্রতিটা ধাপের ছবি

python3 bench/generate.py                      # benchmark তৈরি (seed-নির্দিষ্ট)
python3 bench/score.py --engine raw            # সাধারণ Tesseract
python3 bench/score.py --engine ps             # Personal Scanner
python3 bench/score.py --engine ps --show --filter table-01   # বিস্তারিত
```

CI (`.github/workflows/personal-scanner-core.yml`) প্রতিটা পরিবর্তনে benchmark চালায়; নির্ভুলতা
নির্দিষ্ট সীমার নিচে নামলে ব্যর্থ হয়।

## গঠন

```
core/include/ps/engine.hpp   পাবলিক API (Engine, Page, Block, Cell)
core/src/imaging.*           পাতা খোঁজা, আলো, দিক, হেলানো, দাগ
core/src/tables.*            ছকের ঘর খোঁজা
core/src/engine.cpp          পুরো প্রক্রিয়া ও পুনঃপাঠ
core/src/text.*              UTF-8 ও অঙ্ক-বিশ্লেষণ
tools/ps_ocr.cpp             কমান্ড-লাইন টুল
bench/generate.py            কৃত্রিম কাগজ তৈরি
bench/score.py               নির্ভুলতা মাপা
bench/reference/             Manus-এর ৩টা নমুনা (সংশোধিত উত্তরসহ)
```

## পরের ধাপ

1. GitHub Actions-এ Android APK (Flutter + এই ইঞ্জিন), `tessdata_best` মডেল
2. দাগহীন টেবিল (যেমন Import Permit) কলাম ধরে পড়া
3. বাংলা শব্দতালিকা দিয়ে বানান সংশোধন (ঋ/খ, চন্দ্রবিন্দু, ূ/ু)
4. সার্চ করা যায় এমন PDF (ছবির নিচে অদৃশ্য লেখা), আসল .docx, Excel
5. মূসক-৬.৩, UD, UP ফর্মের নির্দিষ্ট ঘর ধরে পড়া
