import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:share_plus/share_plus.dart';
import '../doc_store.dart';
import '../export/docx_writer.dart';
import '../export/pdf_writer.dart';
import '../export/xlsx_writer.dart';
import '../models.dart';
import '../ocr/ocr_engine.dart';
import '../ocr/ocr_queue.dart';
import 'page_manager_screen.dart';

/// একটা ডকুমেন্টের পাতাগুলো দেখানো + "OCR শুরু করুন" (১০০-পাতা ব্যাচ, progress
/// bar সহ, resume-যোগ্য) + Word/Excel/PDF export + পেজ ম্যানেজমেন্ট (delete/extract)।
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

  Future<void> _export(String kind) async {
    final dir = await DocStore.appDir();
    final outDir = Directory(p.join(dir.path, 'exports'));
    if (!await outDir.exists()) await outDir.create(recursive: true);

    File file;
    switch (kind) {
      case 'docx':
        file = File(p.join(outDir.path, '${_doc.title}.docx'));
        await file.writeAsBytes(DocxWriter().build(_doc));
      case 'xlsx':
        file = File(p.join(outDir.path, '${_doc.title}.xlsx'));
        await file.writeAsBytes(XlsxWriter().build(_doc));
      case 'pdf':
        file = File(p.join(outDir.path, '${_doc.title}.pdf'));
        await file.writeAsBytes(await PdfWriter().build(_doc));
      default:
        return;
    }
    await Share.shareXFiles([XFile(file.path)]);
  }

  @override
  Widget build(BuildContext context) {
    final doc = _doc;
    final pending = doc.pages.where((p) => !p.ocrDone).length;

    return Scaffold(
      appBar: AppBar(
        title: Text(doc.title),
        actions: [
          IconButton(
            tooltip: 'পেজ ম্যানেজ করুন',
            icon: const Icon(Icons.dashboard_customize_outlined),
            onPressed: () async {
              await Navigator.push(context,
                  MaterialPageRoute(builder: (_) => PageManagerScreen(store: widget.store, documentId: doc.id)));
              setState(() {});
            },
          ),
        ],
      ),
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
                    page.hasImage
                        ? Image.file(File(page.imagePath!), fit: BoxFit.cover, cacheWidth: 240)
                        : Container(
                            color: Colors.black12,
                            child: const Icon(Icons.description_outlined),
                          ),
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
                OutlinedButton.icon(onPressed: () => _export('docx'), icon: const Icon(Icons.description), label: const Text('Word')),
                OutlinedButton.icon(onPressed: () => _export('xlsx'), icon: const Icon(Icons.table_chart), label: const Text('Excel')),
                OutlinedButton.icon(onPressed: () => _export('pdf'), icon: const Icon(Icons.picture_as_pdf), label: const Text('PDF')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
