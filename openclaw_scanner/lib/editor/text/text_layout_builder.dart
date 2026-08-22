import 'dart:ui';
import '../../data/db/app_database.dart';
import 'text_block_model.dart';

class _Line {
  _Line(this.rect, this.text, this.height);
  final Rect rect;
  final String text;
  final double height;
}

class TextLayoutBuilder {
  /// Word-level OCR box থেকে editable paragraph block বানায়।
  static List<EditableTextBlock> build(List<OcrBlock> words) {
    if (words.isEmpty) return const [];

    final byLine = <String, List<OcrBlock>>{};
    for (final w in words) {
      final key = w.lineId ?? _yBand(w.y);
      (byLine[key] ??= []).add(w);
    }

    final lines = <_Line>[];
    for (final group in byLine.values) {
      group.sort((a, b) => a.x.compareTo(b.x));
      final left = group.map((w) => w.x).reduce(_min);
      final top = group.map((w) => w.y).reduce(_min);
      final right = group.map((w) => w.x + w.w).reduce(_max);
      final bottom = group.map((w) => w.y + w.h).reduce(_max);
      final text = group.map((w) => w.text).join(' ');
      lines.add(_Line(Rect.fromLTRB(left, top, right, bottom), text, bottom - top));
    }
    lines.sort((a, b) => a.rect.top.compareTo(b.rect.top));

    final medianH = _median(lines.map((l) => l.height).toList());
    final blocks = <List<_Line>>[];
    for (final line in lines) {
      if (blocks.isEmpty) { blocks.add([line]); continue; }
      final prev = blocks.last.last;
      final gap = line.rect.top - prev.rect.bottom;
      final overlapX = _overlap(line.rect.left, line.rect.right, prev.rect.left, prev.rect.right);
      (gap <= medianH * 1.6 && overlapX > 0.2) ? blocks.last.add(line) : blocks.add([line]);
    }

    var i = 0;
    return [
      for (final b in blocks)
        EditableTextBlock(
          id: 'tb_${i++}',
          rectN: _union(b.map((l) => l.rect)),
          fontSizeN: _median(b.map((l) => l.height).toList()) * 0.92,
          text: b.map((l) => l.text).join('\n'),
          align: _alignOf(_union(b.map((l) => l.rect))),
        ),
    ];
  }

  static String _yBand(double y) => (y * 100).round().toString();
  static double _min(double a, double b) => a < b ? a : b;
  static double _max(double a, double b) => a > b ? a : b;

  static double _overlap(double a0, double a1, double b0, double b1) {
    final inter = _min(a1, b1) - _max(a0, b0);
    final minW = _min(a1 - a0, b1 - b0);
    return minW <= 0 ? 0 : (inter / minW).clamp(0, 1);
  }

  static Rect _union(Iterable<Rect> rects) {
    var r = rects.first;
    for (final o in rects.skip(1)) r = r.expandToInclude(o);
    return r;
  }

  static double _median(List<double> xs) {
    final s = [...xs]..sort();
    return s[s.length ~/ 2];
  }

  static TextAlignH _alignOf(Rect n) {
    final leftGap = n.left, rightGap = 1 - n.right;
    if ((leftGap - rightGap).abs() < 0.05) return TextAlignH.center;
    return rightGap < leftGap ? TextAlignH.right : TextAlignH.left;
  }
}
