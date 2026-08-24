# Assets (user-supplied)

These binaries are **not** committed to git (they are large and/or
license-restricted). Drop the real files here before `flutter build`.
`pubspec.yaml` already declares them; `lib/app/app_paths.dart` copies them to
app-support storage on first launch so the native core can read them from disk.

| Path | What | Where to get it |
| --- | --- | --- |
| `tessdata/ben.traineddata` | Tesseract Bengali LSTM model | tessdata_best / tessdata repo (`ben.traineddata`) |
| `models/lama_fp16.onnx` | LaMa inpainting model (Magic Eraser) | LaMa ONNX export, fp16 |
| `models/handseg_xnnpack.onnx` | Hand/finger segmentation model | hand-segmentation ONNX export |
| `fonts/NotoSansBengali-Regular.ttf` | Bengali UI font | Google Fonts — Noto Sans Bengali |
| `fonts/NotoSansBengali-Bold.ttf` | Bengali UI font (bold) | Google Fonts — Noto Sans Bengali |

See `../BUILD_GUIDE.md` §3 for the full provisioning steps.
