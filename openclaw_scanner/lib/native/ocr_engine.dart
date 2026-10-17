import 'dart:convert';
import 'dart:ffi';
import '../data/db/app_database.dart';
import '../data/db/converters.dart';
import 'scanner_core.dart';
import 'scanner_core_bindings.g.dart';

/// Native Tesseract engine wrapper — JSON block → drift companion।
class NativeOcrEngine {
  NativeOcrEngine(this._core, {required String tessdataDir, String lang = 'ben'})
      : _handle = _core.ocrCreate(tessdataDir, lang);

  final ScannerCore _core;
  final Pointer<ScOcrEngine> _handle;

  List<OcrBlocksCompanion> recognize(Pointer<ScImage> img, String pageId) {
    final jsonStr = _core.ocrRecognize(_handle, img);
    final blocks = (jsonDecode(jsonStr) as List).cast<Map<String, dynamic>>();
    return blocks
        .map((b) => OcrBlocksCompanion.insert(
              id: 'blk_${pageId}_${b['line']}_${(b['x'] as num).toStringAsFixed(4)}',
              pageId: pageId,
              text: b['text'] as String,
              x: (b['x'] as num).toDouble(),
              y: (b['y'] as num).toDouble(),
              w: (b['w'] as num).toDouble(),
              h: (b['h'] as num).toDouble(),
              confidence: Value((b['conf'] as num).toDouble()),
              lineId: Value(b['line'] as String?),
              source: const Value(TextSource.typed), // Phase-2 ICR → handwritten
            ))
        .toList();
  }

  void dispose() => _core.ocrDestroy(_handle);
}
