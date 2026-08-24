import 'dart:ui';

enum MaskMode { add, subtract }
enum AutoKind { shadow, finger, stray }

sealed class MaskOp {
  const MaskOp(this.mode);
  final MaskMode mode;
}

/// Freehand brush: normalized polyline + normalized radius (image width-এর ভগ্নাংশ)।
class BrushOp extends MaskOp {
  const BrushOp(super.mode, {required this.points, required this.radius});
  final List<Offset> points;
  final double radius;
}

class LassoOp extends MaskOp {
  const LassoOp(super.mode, {required this.polygon});
  final List<Offset> polygon;
}

/// Auto-detected region — detection সময়ে normalized contour-এ vectorized।
class AutoOp extends MaskOp {
  const AutoOp(super.mode, {required this.kind, required this.contours});
  final AutoKind kind;
  final List<List<Offset>> contours;
}

class MaskDocument {
  const MaskDocument({required this.ops, this.featherPx = 3, this.dilatePx = 2});
  final List<MaskOp> ops;
  final double featherPx;
  final double dilatePx;
  bool get isEmpty => ops.isEmpty;
}
