# Build Guide (সংক্ষিপ্ত)

## ০. পূর্বশর্ত
- Flutter 3.24+, Android Studio + NDK 27.x + CMake 3.22.1
- (ffigen-এর জন্য) LLVM/libclang
- iOS-এর জন্য: Mac + Xcode + CocoaPods

## ১. খালি project + এই কোড overlay
```
flutter create --org ai.openclaw openclaw_scanner
# এই ZIP-এর সব file একই path-এ কপি করুন
flutter pub get
```

## ২. Third-party native libs (আপনাকে জোগাড় করতে হবে)
`native/third_party/`-তে রাখুন:
- opencv (Android SDK) — `opencv/sdk/native/jni`
- tesseract, leptonica — `.so` per ABI (`lib/<abi>/`)
- onnxruntime — `libonnxruntime.so` per ABI + headers
- pdfium — `libpdfium.so` per ABI (`pdfium/lib/<abi>/`) + headers (`pdfium/include/` containing `fpdfview.h`, `fpdf_edit.h`, `fpdf_ppo.h`, `fpdf_save.h`, `fpdf_text.h`)
- dart — Flutter SDK-এর `dart-sdk/include` (dart_api_dl.c/h)

## ৩. AI model + font (assets-এ রাখুন)
- `assets/tessdata/ben.traineddata`
- `assets/models/lama_fp16.onnx`, `assets/models/handseg_xnnpack.onnx`
- `assets/fonts/NotoSansBengali-Regular.ttf` + `-Bold.ttf`

## ৪. Codegen
```
dart run ffigen --config ffigen.yaml
dart run build_runner build --delete-conflicting-outputs
```

## ৫. Android build
```
flutter run                       # ফোনে debug
flutter build apk --release       # release APK
```

## ৬. iOS build (Mac)
```
./scripts/build_ios.sh            # xcframework
cd ios && pod install && cd ..
flutter build ipa --release
```

## Permissions
- Android `AndroidManifest.xml`: `<uses-permission android:name="android.permission.CAMERA"/>`
- iOS `Info.plist`: `NSCameraUsageDescription`

## ⚠️ নোট
- `sc_pdf.cpp` এখন সম্পূর্ণ implemented (PDFium) — শুধু prebuilt `libpdfium` + headers `third_party/pdfium/`-তে দিতে হবে।
- `sc_analyze.cpp`-এ finger-seg (ONNX) অংশ এখনো TODO; shadow/stray classical অংশ চলে।
- "সহজ পথে" আগে ক্যামেরা+লাইব্রেরি চালান; OCR/Eraser/PDF-এর জন্য native lib লাগবে।
