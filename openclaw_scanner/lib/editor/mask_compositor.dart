import 'dart:io';
import 'dart:ui' as ui;
import 'package:path/path.dart' as p;
import 'mask_model.dart';

/// Normalized ops → FULL-RES grayscale mask PNG (সাদা = erase)।
/// MagicErasePool.applyErase এই path consume করে।
class MaskCompositor {
  MaskCompositor(this.masksDir);
  final Directory masksDir;

  Future<String> composeToFile({
    required String pageId,
    required int width,
    required int height,
    required MaskDocument doc,
  }) async {
    final image = await _rasterize(width, height, doc);
    final png = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    final file = File(p.join(
        masksDir.path, '${pageId}_mask_${DateTime.now().millisecondsSinceEpoch}.png'));
    await file.writeAsBytes(png!.buffer.asUint8List(), flush: true);
    return file.path;
  }

  Future<ui.Image> _rasterize(int w, int h, MaskDocument doc) async {
    final recorder = ui.PictureRecorder();
    final canvas = ui.Canvas(recorder, ui.Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()));
    canvas.drawColor(const ui.Color(0xFF000000), ui.BlendMode.src); // keep

    final growPx = doc.dilatePx;
    for (final op in doc.ops) {
      final erase = op.mode == MaskMode.add;
      final color = erase ? const ui.Color(0xFFFFFFFF) : const ui.Color(0xFF000000);
      final fill = ui.Paint()
        ..color = color
        ..isAntiAlias = true
        ..blendMode = ui.BlendMode.src;
      switch (op) {
        case BrushOp b:
          _drawBrush(canvas, b, w, h, growPx, fill);
        case LassoOp l:
          _drawPoly(canvas, [l.polygon], w, h, growPx, fill);
        case AutoOp a:
          _drawPoly(canvas, a.contours, w, h, growPx, fill, evenOdd: true);
      }
    }

    final picture = recorder.endRecording();
    final raw = await picture.toImage(w, h);
    picture.dispose();
    if (doc.featherPx <= 0) return raw;
    return _feather(raw, w, h, doc.featherPx);
  }

  void _drawBrush(ui.Canvas c, BrushOp b, int w, int h, double grow, ui.Paint fill) {
    final r = b.radius * w + grow;
    final pts = [for (final n in b.points) ui.Offset(n.dx * w, n.dy * h)];
    if (pts.length == 1) { c.drawCircle(pts.first, r, fill); return; }
    final path = ui.Path()..moveTo(pts.first.dx, pts.first.dy);
    for (final pt in pts.skip(1)) path.lineTo(pt.dx, pt.dy);
    c.drawPath(path, ui.Paint()
      ..color = fill.color
      ..blendMode = fill.blendMode
      ..style = ui.PaintingStyle.stroke
      ..strokeWidth = r * 2
      ..strokeCap = ui.StrokeCap.round
      ..strokeJoin = ui.StrokeJoin.round
      ..isAntiAlias = true);
  }

  void _drawPoly(ui.Canvas c, List<List<ui.Offset>> polysN, int w, int h,
      double grow, ui.Paint fill, {bool evenOdd = false}) {
    final path = ui.Path()
      ..fillType = evenOdd ? ui.PathFillType.evenOdd : ui.PathFillType.nonZero;
    for (final poly in polysN) {
      if (poly.isEmpty) continue;
      path.moveTo(poly.first.dx * w, poly.first.dy * h);
      for (final n in poly.skip(1)) path.lineTo(n.dx * w, n.dy * h);
      path.close();
    }
    c.drawPath(path, fill);
    if (grow > 0) {
      c.drawPath(path, ui.Paint()
        ..color = fill.color
        ..blendMode = fill.blendMode
        ..style = ui.PaintingStyle.stroke
        ..strokeWidth = grow * 2
        ..strokeJoin = ui.StrokeJoin.round
        ..isAntiAlias = true);
    }
  }

  Future<ui.Image> _feather(ui.Image src, int w, int h, double sigma) async {
    final recorder = ui.PictureRecorder();
    ui.Canvas(recorder).drawImage(src, ui.Offset.zero, ui.Paint()
      ..imageFilter = ui.ImageFilter.blur(sigmaX: sigma, sigmaY: sigma));
    src.dispose();
    return recorder.endRecording().toImage(w, h);
  }
}
