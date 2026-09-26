import 'dart:io';
import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

/// আপলোড করা .docx ফাইল থেকে সরাসরি টেক্সট বের করে — OCR লাগে না, কারণ এটা
/// আগে থেকেই ডিজিটাল টেক্সট। `word/document.xml` পড়ে প্রতিটা paragraph
/// (`w:p`)-এর ভেতরের সব text-run (`w:t`) জোড়া দেওয়া হয়।
class DocxReader {
  Future<String> extractText(String filePath) async {
    final bytes = await File(filePath).readAsBytes();
    final archive = ZipDecoder().decodeBytes(bytes);

    final candidates = archive.files.where((f) => f.name == 'word/document.xml');
    if (candidates.isEmpty) {
      throw const FormatException('word/document.xml পাওয়া যায়নি — এটা কি সত্যই .docx ফাইল?');
    }
    final xmlStr = String.fromCharCodes(candidates.first.content as List<int>);
    final doc = XmlDocument.parse(xmlStr);

    final paragraphs = <String>[];
    for (final p in doc.findAllElements('w:p')) {
      final buf = StringBuffer();
      for (final t in p.findAllElements('w:t')) {
        buf.write(t.innerText);
      }
      if (buf.isNotEmpty) paragraphs.add(buf.toString());
    }
    return paragraphs.join('\n');
  }
}
