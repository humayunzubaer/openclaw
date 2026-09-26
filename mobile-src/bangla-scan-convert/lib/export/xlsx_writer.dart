import 'dart:typed_data';
import 'package:xml/xml.dart';
import '../models.dart';
import 'ooxml_util.dart';

/// প্রতিটা পাতার প্রতিটা লাইন → এক row, একটা কলামে। জটিল column-detection নেই —
/// MVP-তে "কপি করে কাজে লাগানো যায় এমন Excel" যথেষ্ট।
class XlsxWriter {
  Uint8List build(ScanDocument document) {
    final rows = <String>[];
    for (final page in document.pages) {
      final text = (page.ocrText ?? '').trim();
      if (text.isEmpty) continue;
      rows.addAll(text.split('\n').where((l) => l.trim().isNotEmpty));
    }

    final shared = <String, int>{};
    int intern(String s) => shared.putIfAbsent(s, () => shared.length);

    final sheet = XmlBuilder();
    sheet.processing('xml', 'version="1.0" encoding="UTF-8" standalone="yes"');
    sheet.element('worksheet', attributes: {'xmlns': _sml}, nest: () {
      sheet.element('sheetData', nest: () {
        for (var r = 0; r < rows.length; r++) {
          sheet.element('row', attributes: {'r': '${r + 1}'}, nest: () {
            sheet.element('c', attributes: {
              'r': 'A${r + 1}', 't': 's', 's': '1',
            }, nest: () => sheet.element('v', nest: '${intern(rows[r])}'));
          });
        }
      });
    });

    final ss = StringBuffer('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="$_sml" count="${shared.length}" uniqueCount="${shared.length}">');
    for (final e in (shared.entries.toList()..sort((a, b) => a.value.compareTo(b.value)))) {
      ss.write('<si><t xml:space="preserve">${xmlEscape(e.key)}</t></si>');
    }
    ss.write('</sst>');

    return zipOoxml({
      '[Content_Types].xml': _ct,
      '_rels/.rels': _rels,
      'xl/workbook.xml': _workbook,
      'xl/_rels/workbook.xml.rels': _wbRels,
      'xl/worksheets/sheet1.xml': sheet.buildDocument().toXmlString(),
      'xl/sharedStrings.xml': ss.toString(),
      'xl/styles.xml': _stylesBengali,
    });
  }
}

const _sml = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const _ct = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>''';
const _rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''';
const _workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>''';
const _wbRels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''';
const _stylesBengali = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><sz val="11"/><name val="Noto Sans Bengali"/></font></fonts>
<fills count="1"><fill><patternFill patternType="none"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" applyFont="1"/></cellXfs>
</styleSheet>''';
