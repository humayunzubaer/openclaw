import 'dart:ui';
import '../../data/db/converters.dart';

enum TextAlignH { left, center, right }

/// OCR word থেকে reconstruct করা editable region. Geometry normalized (0..1)।
class EditableTextBlock {
  EditableTextBlock({
    required this.id,
    required this.rectN,
    required this.fontSizeN, // image HEIGHT-এর ভগ্নাংশ
    required this.text,
    this.align = TextAlignH.left,
    this.source = TextSource.typed,
  });

  final String id;
  Rect rectN;
  double fontSizeN;
  String text;
  TextAlignH align;
  TextSource source;

  Map<String, dynamic> toJson() => {
        'id': id,
        'rectN': [rectN.left, rectN.top, rectN.width, rectN.height],
        'fontSizeN': fontSizeN,
        'align': align.name,
        'text': text,
        'source': source.name,
      };

  factory EditableTextBlock.fromJson(Map<String, dynamic> j) {
    final r = (j['rectN'] as List).cast<num>();
    return EditableTextBlock(
      id: j['id'] as String,
      rectN: Rect.fromLTWH(r[0].toDouble(), r[1].toDouble(), r[2].toDouble(), r[3].toDouble()),
      fontSizeN: (j['fontSizeN'] as num).toDouble(),
      text: j['text'] as String,
      align: TextAlignH.values.byName(j['align'] as String? ?? 'left'),
      source: TextSource.values.byName(j['source'] as String? ?? 'typed'),
    );
  }
}
