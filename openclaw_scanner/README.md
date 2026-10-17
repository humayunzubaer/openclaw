# OpenClaw Scanner — Offline-First Bengali Document Scanner

Flutter + C++ (OpenCV / Tesseract / ONNX) দিয়ে তৈরি একটি offline scanner অ্যাপ।

## এই bundle-এ কী আছে (batch অনুযায়ী)

- **Batch 1 (এই ZIP):** project config + app glue
  - `pubspec.yaml`, `ffigen.yaml`
  - `lib/main.dart`
  - `lib/app/` — app, providers, config, background guard, services host, lifecycle
- **Batch 2 (পরে):** database (drift) + native bindings/facade
- **Batch 3 (পরে):** OCR pool + Magic Eraser worker + AppServices
- **Batch 4 (পরে):** editor (Bengali text edit + mask) + auto-analysis
- **Batch 5 (পরে):** export (Word/Excel/JPG) + PDF
- **Batch 6 (পরে):** native C++ core + CMake + iOS xcframework/podspec

## আপনাকে যা আলাদাভাবে জোগাড় করতে হবে (কোডে নেই)

1. **Native prebuilt libraries** (Android): OpenCV, Tesseract, Leptonica, ONNX Runtime
2. **AI models:** `ben.traineddata` (Tesseract Bengali), `lama_fp16.onnx`, `handseg_xnnpack.onnx`
3. **Font:** Noto Sans Bengali (Regular + Bold) `.ttf`

## কীভাবে ব্যবহার করবেন

1. আগে `flutter create --org ai.openclaw openclaw_scanner` দিয়ে একটা খালি project বানান।
2. তারপর এই ZIP-এর file-গুলো ওই project-এ একই path-এ কপি করুন (overwrite)।
3. প্রতিটা batch যোগ করার পর `flutter pub get` চালান।

> ⚠️ স্মরণ করিয়ে দিই: আমরা "সহজ পথে" যাচ্ছি — আগে ছোট চলন্ত অ্যাপ, পরে একটা একটা করে feature। তাই সব batch একসাথে না বসিয়ে ধাপে ধাপে integrate করব। কোন file কখন বসবে, আমি বলে দেব।
