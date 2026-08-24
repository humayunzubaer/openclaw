import 'dart:ffi';
import 'dart:io';
import 'package:ffi/ffi.dart';
import 'scanner_core_bindings.g.dart';

class ScException implements Exception {
  ScException(this.code, this.message);
  final int code;
  final String message;
  @override
  String toString() => 'ScException($code): $message';
}

/// Generated ScannerCoreBindings-এর উপর thin, ergonomic facade।
/// প্রতি isolate-এ একবার instantiate করুন।
class ScannerCore {
  ScannerCore._(this.b);
  final ScannerCoreBindings b;

  factory ScannerCore.open() {
    final lib = Platform.isAndroid
        ? DynamicLibrary.open('libscanner_core.so')
        : DynamicLibrary.process(); // iOS: statically linked
    return ScannerCore._(ScannerCoreBindings(lib));
  }

  void _check(ScStatus st) {
    if (st.code != 0) throw ScException(st.code, st.message.cast<Utf8>().toDartString());
  }

  // process init (একবার)
  void initDartApi() => b.sc_init_dart_api(NativeApi.initializeApiDLData);

  // scratch arena
  Pointer<ScScratch> scratchCreate(int maxBytes) {
    final out = calloc<Pointer<ScScratch>>();
    try {
      _check(b.sc_scratch_create(maxBytes, out));
      return out.value;
    } finally {
      calloc.free(out);
    }
  }
  void scratchReset(Pointer<ScScratch> s) => b.sc_scratch_reset(s);
  void scratchDestroy(Pointer<ScScratch> s) => b.sc_scratch_destroy(s);

  // OCR
  Pointer<ScOcrEngine> ocrCreate(String tessdataDir, String lang) {
    final d = tessdataDir.toNativeUtf8(), l = lang.toNativeUtf8();
    final out = calloc<Pointer<ScOcrEngine>>();
    try {
      _check(b.sc_ocr_create(d.cast(), l.cast(), out));
      return out.value;
    } finally {
      calloc.free(d); calloc.free(l); calloc.free(out);
    }
  }
  String ocrRecognize(Pointer<ScOcrEngine> e, Pointer<ScImage> page) {
    final out = calloc<Pointer<Char>>();
    try {
      _check(b.sc_ocr_recognize(e, page, out));
      final json = out.value.cast<Utf8>().toDartString();
      b.sc_string_free(out.value);
      return json;
    } finally {
      calloc.free(out);
    }
  }
  void ocrDestroy(Pointer<ScOcrEngine> e) => b.sc_ocr_destroy(e);

  // LaMa inpaint (shared session)
  Pointer<ScInpainter> inpaintCreate(String modelPath, int accel) {
    final p = modelPath.toNativeUtf8();
    final out = calloc<Pointer<ScInpainter>>();
    try {
      _check(b.sc_inpaint_create(p.cast(), accel, out));
      return out.value;
    } finally {
      calloc.free(p); calloc.free(out);
    }
  }
  void inpaintRunScratchAsync(Pointer<ScInpainter> inp, Pointer<ScScratch> s,
      Pointer<ScImage> src, Pointer<ScImage> mask, int tile, int overlap, int port, Pointer<ScImage> out) {
    _check(b.sc_inpaint_run_scratch_async(inp, s, src, mask, tile, overlap, port, out));
  }
  void inpaintDestroy(Pointer<ScInpainter> inp) => b.sc_inpaint_destroy(inp);

  // Hand seg + auto analyze
  Pointer<ScHandSegmenter> handSegCreate(String modelPath, int accel) {
    final p = modelPath.toNativeUtf8();
    final out = calloc<Pointer<ScHandSegmenter>>();
    try {
      _check(b.sc_handseg_create(p.cast(), accel, out));
      return out.value;
    } finally {
      calloc.free(p); calloc.free(out);
    }
  }
  void handSegDestroy(Pointer<ScHandSegmenter> hs) => b.sc_handseg_destroy(hs);

  String autoAnalyze(Pointer<ScHandSegmenter> hs, Pointer<ScScratch> s, String srcPath, int maxDim) {
    final p = srcPath.toNativeUtf8();
    final out = calloc<Pointer<Char>>();
    try {
      _check(b.sc_auto_analyze(hs, s, p.cast(), maxDim, out));
      final json = out.value.cast<Utf8>().toDartString();
      b.sc_string_free(out.value);
      return json;
    } finally {
      calloc.free(p); calloc.free(out);
    }
  }

  // PDF
  void pdfInit() => b.sc_pdf_init();
  void pdfAddTextLayer(String pdfIn, String pdfOut, String fontPath, String json) {
    final a = pdfIn.toNativeUtf8(), c = pdfOut.toNativeUtf8();
    final f = fontPath.toNativeUtf8(), j = json.toNativeUtf8();
    try {
      _check(b.sc_pdf_add_text_layer(a.cast(), c.cast(), f.cast(), j.cast()));
    } finally {
      calloc.free(a); calloc.free(c); calloc.free(f); calloc.free(j);
    }
  }
}
