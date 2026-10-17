import 'dart:convert';
import 'dart:ffi';
import 'dart:isolate';
import 'dart:ui' show Offset;

import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';
import 'mask_model.dart';

class AutoAnalyzer {
  AutoAnalyzer._(this._handSegAddr);
  final int _handSegAddr;

  static AutoAnalyzer boot({required String handSegModelPath}) {
    final core = ScannerCore.open();
    final hs = core.handSegCreate(handSegModelPath, ScAccel.SC_XNNPACK.value);
    return AutoAnalyzer._(hs.address);
  }

  /// Editor open-এ suggested mask; heavy কাজ throwaway isolate-এ, contour normalized।
  Future<List<AutoOp>> analyze({required String sourcePath, int maxDim = 1024}) async {
    final json = await Isolate.run(() => _analyzeInIsolate(_handSegAddr, sourcePath, maxDim));
    return _parse(json);
  }

  void dispose() =>
      ScannerCore.open().handSegDestroy(Pointer<ScHandSegmenter>.fromAddress(_handSegAddr));
}

String _analyzeInIsolate(int handSegAddr, String srcPath, int maxDim) {
  final core = ScannerCore.open();
  final scratch = core.scratchCreate(16 << 20);
  try {
    return core.autoAnalyze(
        Pointer<ScHandSegmenter>.fromAddress(handSegAddr), scratch, srcPath, maxDim);
  } finally {
    core.scratchDestroy(scratch);
  }
}

List<AutoOp> _parse(String jsonStr) {
  final map = jsonDecode(jsonStr) as Map<String, dynamic>;
  final ops = <AutoOp>[];
  for (final entry in map.entries) {
    final kind = switch (entry.key) {
      'shadow' => AutoKind.shadow,
      'finger' => AutoKind.finger,
      _ => AutoKind.stray,
    };
    for (final region in entry.value as List) {
      final rings = [
        for (final ring in region as List)
          [for (final pt in ring as List) _offset(pt as Map<String, dynamic>)],
      ];
      if (rings.isEmpty || rings.first.isEmpty) continue;
      ops.add(AutoOp(MaskMode.add, kind: kind, contours: rings));
    }
  }
  return ops;
}

Offset _offset(Map<String, dynamic> p) =>
    Offset((p['x'] as num).toDouble(), (p['y'] as num).toDouble());
