import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:uuid/uuid.dart';
import '../doc_store.dart';
import '../document/document_screen.dart';
import '../models.dart';

/// গ্যালারি/ফাইল থেকে একটা ছবি (.jpg/.png) বেছে নিয়ে সরাসরি OCR queue-তে ঢোকানো —
/// ক্যামেরা ছাড়াও আগে থেকে তোলা কোনো ছবি OCR করতে চাইলে এটা ব্যবহার হয়।
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
        allowedExtensions: ['jpg', 'jpeg', 'png'],
      );
      if (result == null || result.files.single.path == null) {
        setState(() => _busy = false);
        return;
      }
      final path = result.files.single.path!;
      final title = p.basenameWithoutExtension(path);

      final doc = ScanDocument(
        id: const Uuid().v4(),
        title: title,
        createdAt: DateTime.now(),
        pages: [ScanPage(id: const Uuid().v4(), imagePath: path, source: SourceKind.importedImage)],
      );
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
      appBar: AppBar(title: const Text('ছবি আপলোড করুন')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'একটা ছবি (.jpg/.png) বেছে নিন — সেটাতে "OCR শুরু করুন" চাপলে বাংলা টেক্সট বের হবে।',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              if (_busy) const CircularProgressIndicator(),
              if (!_busy)
                FilledButton.icon(
                  onPressed: _pickAndImport,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('ছবি বেছে নিন'),
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
