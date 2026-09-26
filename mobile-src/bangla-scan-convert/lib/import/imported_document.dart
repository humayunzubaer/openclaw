import 'package:uuid/uuid.dart';
import '../models.dart';
import 'docx_reader.dart';
import 'xlsx_reader.dart';

/// Word/Excel থেকে extract করা টেক্সটকে আমাদের সাধারণ ScanDocument মডেলে
/// রূপান্তর করে — এর ফলে একই export pipeline (docx/xlsx/pdf writer) স্ক্যান
/// করা ও আপলোড করা — দুই ধরনের ডকুমেন্টের জন্যই অভিন্নভাবে কাজ করে।
class ImportedDocument {
  static Future<ScanDocument> fromDocx(String filePath, String title) async {
    final text = await DocxReader().extractText(filePath);
    return _single(title, text, DocumentKind.imported);
  }

  static Future<ScanDocument> fromXlsx(String filePath, String title) async {
    final rows = await XlsxReader().extractRows(filePath);
    final text = rows.map((r) => r.join('  ')).join('\n');
    return _single(title, text, DocumentKind.imported);
  }

  static ScanDocument _single(String title, String text, DocumentKind kind) {
    final page = ScanPage(
      id: const Uuid().v4(),
      imagePath: null, // ছবি নেই — সরাসরি টেক্সট
      ocrText: text,
      ocrDone: true, // ইতিমধ্যে ডিজিটাল টেক্সট, OCR দরকার নেই
      source: SourceKind.importedDocx,
    );
    return ScanDocument(
      id: const Uuid().v4(),
      title: title,
      pages: [page],
      createdAt: DateTime.now(),
      docKind: kind,
    );
  }
}
