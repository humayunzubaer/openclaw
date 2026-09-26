import 'dart:typed_data';
import 'package:xml/xml.dart';
import '../models.dart';
import '../typeset/script_run_splitter.dart';
import '../typeset/sutonny_mj_converter.dart';
import '../typeset/typeset_rule.dart';
import 'ooxml_util.dart';

/// প্রতিটা পাতার OCR টেক্সট → paragraph, কিন্তু এবার **mixed-script aware**:
/// প্রতিটা লাইনের বাংলা অংশ সুতন্বী MJ ফন্টে, ইংরেজি অংশ Times New Roman-এ
/// (বাংলার চেয়ে ২pt ছোট) — আলাদা `w:r` (run) হিসেবে, একই paragraph-এর ভেতরে।
///
/// complex-script run properties (w:cs, w:szCs, w:lang w:bidi) ছাড়া Word ভুল
/// ফন্ট/সাইজে বাংলা দেখায় — তাই এগুলো অবশ্যই রাখা হয়েছে।
class DocxWriter {
  DocxWriter({this.bengaliSizePt = 12});

  final double bengaliSizePt;
  final _converter = SutonnyMjConverter();

  Uint8List build(ScanDocument document) {
    final b = XmlBuilder();
    b.processing('xml', 'version="1.0" encoding="UTF-8" standalone="yes"');
    b.element('w:document', namespaces: {_wns: 'w'}, nest: () {
      b.element('w:body', nest: () {
        for (final page in document.pages) {
          final text = (page.ocrText ?? '').trim();
          if (text.isEmpty) continue;
          for (final line in text.split('\n')) {
            if (line.trim().isEmpty) continue;
            b.element('w:p', nest: () {
              for (final run in ScriptRunSplitter.split(line)) {
                _writeRun(b, run);
              }
            });
          }
          b.element('w:p'); // পাতার মাঝে ফাঁকা লাইন
        }
        b.element('w:sectPr', nest: () {
          b.element('w:pgSz', attributes: {'w:w': '11906', 'w:h': '16838'}); // A4
        });
      });
    });

    return zipOoxml({
      '[Content_Types].xml': _contentTypes,
      '_rels/.rels': _rootRels,
      'word/document.xml': b.buildDocument().toXmlString(),
      'word/_rels/document.xml.rels': _docRels,
    });
  }

  void _writeRun(XmlBuilder b, ScriptRun run) {
    final isBengali = run.kind == ScriptKind.bengali;
    final font = isBengali ? _converter.outputFontFamily : TypesetRule.englishFont;
    final sizePt = isBengali
        ? bengaliSizePt
        : TypesetRule.englishSizeFor(bengaliSizePt);
    final halfPt = (sizePt * 2).round().toString();
    final text = isBengali ? _converter.convert(run.text) : run.text;

    b.element('w:r', nest: () {
      b.element('w:rPr', nest: () {
        b.element('w:rFonts', attributes: {
          'w:ascii': font, 'w:hAnsi': font, 'w:cs': font,
        });
        b.element('w:sz', attributes: {'w:val': halfPt});
        b.element('w:szCs', attributes: {'w:val': halfPt});
        if (isBengali) {
          b.element('w:lang', attributes: {'w:bidi': 'bn-BD'});
        }
      });
      b.element('w:t', attributes: {'xml:space': 'preserve'}, nest: text);
    });
  }
}

const _wns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const _contentTypes = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''';
const _rootRels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''';
const _docRels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>''';
