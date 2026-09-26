import 'dart:io';
import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

/// আপলোড করা .xlsx ফাইল থেকে সরাসরি সেল-টেক্সট বের করে (প্রথম শিট) — OCR
/// লাগে না। `sharedStrings.xml` + `worksheets/sheet1.xml` মিলিয়ে row/cell
/// পুনর্গঠন করে।
class XlsxReader {
  Future<List<List<String>>> extractRows(String filePath) async {
    final bytes = await File(filePath).readAsBytes();
    final archive = ZipDecoder().decodeBytes(bytes);

    final shared = <String>[];
    final sharedFiles = archive.files.where((f) => f.name == 'xl/sharedStrings.xml');
    if (sharedFiles.isNotEmpty) {
      final xml = XmlDocument.parse(String.fromCharCodes(sharedFiles.first.content as List<int>));
      for (final si in xml.findAllElements('si')) {
        shared.add(si.findAllElements('t').map((t) => t.innerText).join());
      }
    }

    final sheetFiles = archive.files.where((f) => f.name == 'xl/worksheets/sheet1.xml');
    if (sheetFiles.isEmpty) {
      throw const FormatException('xl/worksheets/sheet1.xml পাওয়া যায়নি — এটা কি সত্যই .xlsx ফাইল?');
    }
    final sheetXml = XmlDocument.parse(String.fromCharCodes(sheetFiles.first.content as List<int>));

    final rows = <List<String>>[];
    for (final rowEl in sheetXml.findAllElements('row')) {
      final cells = <String>[];
      for (final c in rowEl.findAllElements('c')) {
        final vEls = c.findElements('v');
        if (vEls.isEmpty) { cells.add(''); continue; }
        final raw = vEls.first.innerText;
        if (c.getAttribute('t') == 's') {
          final idx = int.tryParse(raw) ?? -1;
          cells.add(idx >= 0 && idx < shared.length ? shared[idx] : '');
        } else {
          cells.add(raw);
        }
      }
      rows.add(cells);
    }
    return rows;
  }

  Future<String> extractAsText(String filePath) async {
    final rows = await extractRows(filePath);
    return rows.map((r) => r.join('\t')).join('\n');
  }
}
