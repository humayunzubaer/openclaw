import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:uuid/uuid.dart';
import '../doc_store.dart';
import '../document/document_screen.dart';
import '../models.dart';
import 'imported_document.dart';

/// "ফাইল আপলোড করুন" — Word/Excel সরাসরি পড়ে টেক্সট বের করে (OCR ছাড়াই);
/// ছবি (.jpg/.png) আপলোড হলে normal OCR queue-তে ঢোকে (ডকুমেন্ট স্ক্রিনে
/// "OCR শুরু করুন" চাপলে চলবে)।
///
/// ⚠️ সৎ স্কোপ-নোট: .docx, .xlsx, .jpg/.png — এই তিন ফরম্যাট এখন সমর্থিত।
/// .pdf আপলোড থেকে OCR করতে হলে আগে PDF-এর প্রতিটা পাতাকে ছবিতে রূপান্তর
/// করতে হয় — এই অংশটা এখনো তৈরি হয়নি, এটাই "যেকোনো ফরম্যাট ইনপুট"-এর বাকি
/// থাকা অংশ। (PDF থেকে page মুছে ফেলা/এক্সট্র্যাক্ট করা — সেটা আমাদের নিজের
/// এক্সপোর্ট করা ডকুমেন্টের জন্য আগে থেকেই আছে, page manager স্ক্রিনে।)
class ImportScreen extends StatefulWidget {
  const ImportScreen({super.key, required this.store});
  final DocStore store;

  @override
  State<ImportScreen> createState() => _ImportScreenState();
}

class _ImportScreenState extends State<ImportScreen> {
  bool _busy = false;
  String? _error;

  Future<void> _pickAndImport() async {
    setState(() { _busy = true; _error = null; });
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['docx', 'xlsx', 'jpg', 'jpeg', 'png'],
      );
      if (result == null || result.files.single.path == null) {
        setState(() => _busy = false);
        return;
      }
      final path = result.files.single.path!;
      final ext = p.extension(path).toLowerCase();
      final title = p.basenameWithoutExtension(path);

      final doc = switch (ext) {
        '.docx' => await ImportedDocument.fromDocx(path, title),
        '.xlsx' => await ImportedDocument.fromXlsx(path, title),
        '.jpg' || '.jpeg' || '.png' => ScanDocument(
            id: const Uuid().v4(),
            title: title,
            createdAt: DateTime.now(),
            docKind: DocumentKind.imported,
            pages: [ScanPage(id: const Uuid().v4(), imagePath: path, source: SourceKind.importedImage)],
          ),
        _ => throw UnsupportedError('এই ফরম্যাট এখনো সমর্থিত নয়: $ext'),
      };
      await widget.store.addDocument(doc);

      if (mounted) {
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => DocumentScreen(store: widget.store, documentId: doc.id)));
      }
    } catch (e) {
      setState(() { _error = 'আমদানি ব্যর্থ: $e'; _busy = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ফাইল আপলোড করুন')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Word (.docx), Excel (.xlsx), বা ছবি (.jpg/.png) বেছে নিন। Word/Excel থেকে '
                'সরাসরি টেক্সট বের হয়ে আসবে (OCR লাগবে না); ছবি হলে ডকুমেন্ট স্ক্রিনে '
                '"OCR শুরু করুন" চাপতে হবে।',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              if (_busy) const CircularProgressIndicator(),
              if (!_busy)
                FilledButton.icon(
                  onPressed: _pickAndImport,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('ফাইল বেছে নিন'),
                ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
