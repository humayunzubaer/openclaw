import 'dart:typed_data';
import 'package:xml/xml.dart';
import '../editor/text/text_block_model.dart';
import 'export_source.dart';
import 'ooxml_util.dart';

/// Real, editable Bengali text .docx — complex-script run props (cs, szCs, bidi)।
class DocxWriter {
  static const _pageHeightPt = 842.0; // A4
  static const _font = 'Noto Sans Bengali';

  Uint8List build(List<PageExport> pages) {
    final b = XmlBuilder();
    b.processing('xml', 'version="1.0" encoding="UTF-8" standalone="yes"');
    b.element('w:document', namespaces: {_wns: 'w'}, nest: () {
      b.element('w:body', nest: () {
        for (final pe in pages) {
          for (final block in pe.blocks) {
            final hp = (block.fontSizeN * _pageHeightPt * 2).round().toString();
            for (final line in block.text.split('\n')) {
              b.element('w:p', nest: () {
                b.element('w:pPr', nest: () {
                  b.element('w:jc', attributes: {'w:val': _jc(block.align)});
                });
                b.element('w:r', nest: () {
                  b.element('w:rPr', nest: () {
                    b.element('w:rFonts', attributes: {
                      'w:ascii': _font, 'w:hAnsi': _font, 'w:cs': _font,
                    });
                    b.element('w:sz', attributes: {'w:val': hp});
                    b.element('w:szCs', attributes: {'w:val': hp});
                    b.element('w:lang', attributes: {'w:bidi': 'bn-BD'});
                  });
                  b.element('w:t', attributes: {'xml:space': 'preserve'}, nest: line);
                });
              });
            }
          }
          b.element('w:p');
        }
        b.element('w:sectPr', nest: () {
          b.element('w:pgSz', attributes: {'w:w': '11906', 'w:h': '16838'});
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

  String _jc(TextAlignH a) => switch (a) {
        TextAlignH.center => 'center',
        TextAlignH.right => 'right',
        TextAlignH.left => 'left',
      };
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
