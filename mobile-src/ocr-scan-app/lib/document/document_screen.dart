import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:share_plus/share_plus.dart';
import '../doc_store.dart';
import '../export/docx_writer.dart';
import '../models.dart';
import '../ocr/ocr_engine.dart';
import '../ocr/ocr_queue.dart';

/// একটা ডকুমেন্টের পাতাগুলো দেখানো + "OCR শুরু করুন" (১০০-পাতা ব্যাচ, progress
/// bar সহ, resume-যোগ্য) + Word export (SutonnyMJ বাংলা + Times New Roman ইংরেজি) + টেক্সট শেয়ার।
class DocumentScreen extends StatefulWidget {
  const DocumentScreen({super.key, required this.store, required this.documentId});
  final DocStore store;
  final String documentId;

  @override
  State<DocumentScreen> createState() => _DocumentScreenState();
}

class _DocumentScreenState extends State<DocumentScreen> {
  late final OcrQueue _queue = OcrQueue(widget.store, OcrEngine());
  bool _running = false;
  int _done = 0;
  int _total = 0;

  ScanDocument get _doc => widget.store.byId(widget.documentId)!;

  Future<void> _runOcr() async {
    setState(() { _running = true; _done = 0; _total = 0; });
    await _queue.runDocument(
      _doc,
      onProgress: (done, total) {
        if (!mounted) return;
        setState(() { _done = done; _total = total; });
      },
    );
    if (mounted) setState(() => _running = false);
  }

  Future<void> _exportDocx() async {
    final dir = await DocStore.appDir();
    final outDir = Directory(p.join(dir.path, 'exports'));
    if (!await outDir.exists()) await outDir.create(recursive: true);
    final file = File(p.join(outDir.path, '${_doc.title}.docx'));
    await file.writeAsBytes(DocxWriter().build(_doc));
    await Share.shareXFiles([XFile(file.path)]);
  }

  Future<void> _shareText() async {
    final text = _doc.pages.map((p) => p.ocrText ?? '').join('\n\n');
    await Share.share(text);
  }

  @override
  Widget build(BuildContext context) {
    final doc = _doc;
    final pending = doc.pages.where((p) => !p.ocrDone).length;

    return Scaffold(
      appBar: AppBar(title: Text(doc.title)),
      body: Column(
        children: [
          if (_running)
            LinearProgressIndicator(value: _total == 0 ? null : _done / _total),
          if (_running)
            Padding(padding: const EdgeInsets.all(8), child: Text('OCR হচ্ছে: $_done/$_total')),
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.all(8),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 3),
              itemCount: doc.pages.length,
              itemBuilder: (context, i) {
                final page = doc.pages[i];
                return Stack(
                  fit: StackFit.expand,
                  children: [
                    // cacheWidth: grid-এ full-res decode না করে ছোট সাইজেই — স্মুথ scroll
                    Image.file(File(page.imagePath), fit: BoxFit.cover, cacheWidth: 240),
                    if (page.ocrDone)
                      const Positioned(
                        right: 4, top: 4,
                        child: Icon(Icons.check_circle, color: Colors.green, size: 18),
                      ),
                  ],
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8, runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: _running || pending == 0 ? null : _runOcr,
                  icon: const Icon(Icons.text_fields),
                  label: Text(pending == 0 ? 'OCR সম্পন্ন' : 'OCR শুরু করুন ($pending বাকি)'),
                ),
                OutlinedButton.icon(
                    onPressed: doc.ocrComplete ? _exportDocx : null,
                    icon: const Icon(Icons.description),
                    label: const Text('Word-এ Export')),
                OutlinedButton.icon(
                    onPressed: doc.ocrComplete ? _shareText : null,
                    icon: const Icon(Icons.ios_share),
                    label: const Text('টেক্সট শেয়ার')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
