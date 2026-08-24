# Next Steps

The **complete code bundle** (batches 1–6) is now integrated under
`openclaw_scanner/`. What remains cannot be done in this cloud session — it
needs your local machine (Flutter SDK, Android/iOS toolchains) and a few
third-party binaries that are too large / license-restricted to commit. This
file is the exact checklist to get from here to a running app.

## 1. Finish local environment (you were stuck here)

```powershell
# Download the Flutter SDK zip, extract to C:\src\flutter
# Add C:\src\flutter\bin to PATH, open a NEW PowerShell, then:
flutter --version
flutter doctor            # resolve every ✗ before continuing
flutter devices           # phone in USB-debugging mode should appear
```

## 2. Create the platform shell, then overlay this code

`flutter create` generates the `android/`, `ios/`, `web/` folders (they are
**not** in git — see `.gitignore`). Create an empty app with the same org and
name, then copy this repo's `openclaw_scanner/` files over it:

```bash
flutter create --org ai.openclaw openclaw_scanner
# copy every file from this folder into that project at the same path (overwrite)
flutter pub get
```

## 3. Drop in the user-supplied binaries

- **Native prebuilt libs** → `native/third_party/` (OpenCV, Tesseract,
  Leptonica, ONNX Runtime, **PDFium** — `libpdfium` + headers under
  `third_party/pdfium/`; Dart API headers from the Flutter SDK).
  See `BUILD_GUIDE.md` §2.
- **AI models + fonts** → `assets/` (see `assets/README.md`):
  `tessdata/ben.traineddata`, `models/lama_fp16.onnx`,
  `models/handseg_xnnpack.onnx`, `fonts/NotoSansBengali-{Regular,Bold}.ttf`.

## 4. Code generation

```bash
dart run ffigen --config ffigen.yaml                 # -> lib/native/scanner_core_bindings.g.dart
dart run build_runner build --delete-conflicting-outputs   # -> app_database.g.dart
```

## 5. Platform permissions (add to the generated shell)

- Android `android/app/src/main/AndroidManifest.xml`:
  `<uses-permission android:name="android.permission.CAMERA"/>`
- iOS `ios/Runner/Info.plist`: `NSCameraUsageDescription` string.

## 6. Run

```bash
flutter run                    # debug on the connected phone (Milestone 1)
flutter build apk --release    # Android release
./scripts/build_ios.sh && cd ios && pod install && cd .. && flutter build ipa --release  # iOS (Mac)
```

## Known code TODOs (need external libs before they do anything)

- `native/src/sc_pdf.cpp` — **implemented** against the PDFium C API
  (page count, images→PDF with aspect-fit, page extract/combine, image
  recompress to a target DPI/quality, and an invisible CID-TrueType Bengali
  text layer for searchable PDFs). It needs the prebuilt **PDFium** lib +
  headers under `third_party/pdfium/` (wired in `native/CMakeLists.txt`);
  nothing else to write.
- `native/src/sc_analyze.cpp` — shadow & stray-mark detection and contour
  extraction are implemented; `sc_handseg_create` / `sc_auto_analyze` still
  need the **finger-segmentation ONNX** session (mirror `sc_inpaint.cpp`) and
  the shadow+finger+stray merge into one JSON. This is the only remaining
  native stub; it doesn't block camera capture, the library, OCR, the editor,
  or PDF.

## "সহজ পথে" reminder

Get the small moving app first: camera capture + library on the phone
(Milestone 1). Add OCR, Magic Eraser, export, and PDF one feature at a time —
each needs its native lib present before it lights up.
