import 'dart:ffi';
import 'dart:isolate';
import 'package:ffi/ffi.dart';
import '../data/db/converters.dart';
import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';

class CaptureResult {
  CaptureResult(this.procPath, this.thumbPath, this.width, this.height);
  final String procPath, thumbPath;
  final int width, height;
}

void _ck(ScStatus st) { if (st.code != 0) throw StateError('native ${st.code}'); }

/// detect → warp → (dewarp|deshadow) → save + thumbnail, throwaway isolate-এ।
Future<CaptureResult> processCapture({
  required CaptureMode mode,
  required String srcPath,
  required String procPath,
  required String thumbPath,
}) {
  final m = mode;
  return Isolate.run(() {
    final core = ScannerCore.open();
    final b = core.b;
    final scratch = core.scratchCreate(64 << 20);
    final view = calloc<ScImage>(), quad = calloc<ScQuad>();
    final warped = calloc<ScImage>(), cleaned = calloc<ScImage>(), thumb = calloc<ScImage>();
    final cSrc = srcPath.toNativeUtf8(), cProc = procPath.toNativeUtf8(), cThumb = thumbPath.toNativeUtf8();
    try {
      _ck(b.sc_scratch_load_file(scratch, cSrc.cast(), view));
      _ck(b.sc_detect_document_quad(view, quad));
      _ck(b.sc_warp_perspective(view, quad, warped));
      _ck(m == CaptureMode.book
          ? b.sc_dewarp_book(warped, cleaned)
          : b.sc_remove_shadow(warped, cleaned));
      _ck(b.sc_image_save_file(cleaned, cProc.cast(), 92));

      final w = cleaned.ref.width, h = cleaned.ref.height;
      _ck(b.sc_resize(cleaned, 240, (240 * h / w).round(), 1, thumb));
      _ck(b.sc_image_save_file(thumb, cThumb.cast(), 80));

      b.sc_image_free(warped); b.sc_image_free(cleaned); b.sc_image_free(thumb);
      return CaptureResult(procPath, thumbPath, w, h);
    } finally {
      core.scratchDestroy(scratch);
      for (final p in [view, quad, warped, cleaned, thumb]) calloc.free(p);
      for (final p in [cSrc, cProc, cThumb]) calloc.free(p);
    }
  });
}
