import 'dart:io';
import 'package:flutter/material.dart';
import '../capture/scan_screen.dart';
import '../doc_store.dart';
import '../document/document_screen.dart';
import '../import/import_screen.dart';

class LibraryScreen extends StatefulWidget {
  const LibraryScreen({super.key, required this.store});
  final DocStore store;

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  @override
  Widget build(BuildContext context) {
    final docs = widget.store.documents;
    return Scaffold(
      appBar: AppBar(
        title: const Text('OCR Scan'),
        actions: [
          IconButton(
            tooltip: 'ছবি আপলোড করে OCR করুন',
            icon: const Icon(Icons.upload_file),
            onPressed: () async {
              await Navigator.push(
                  context, MaterialPageRoute(builder: (_) => ImportScreen(store: widget.store)));
              setState(() {});
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.push(
              context, MaterialPageRoute(builder: (_) => ScanScreen(store: widget.store)));
          setState(() {});
        },
        icon: const Icon(Icons.add_a_photo),
        label: const Text('নতুন স্ক্যান'),
      ),
      body: docs.isEmpty
          ? const Center(
              child: Text('এখনো কোনো ডকুমেন্ট নেই।\n"নতুন স্ক্যান" চাপুন।', textAlign: TextAlign.center))
          : ListView(children: [
              for (final d in docs)
                ListTile(
                  leading: d.pages.isNotEmpty
                      ? SizedBox(
                          width: 40, height: 52,
                          // cacheWidth: list-এ full-res ছবি decode না করে ছোট সাইজে — স্মুথ scroll
                          child: Image.file(File(d.pages.first.imagePath), fit: BoxFit.cover, cacheWidth: 100),
                        )
                      : const Icon(Icons.description),
                  title: Text(d.title),
                  subtitle: Text('${d.pages.length} পৃষ্ঠা · ${d.ocrComplete ? "OCR সম্পন্ন" : "OCR বাকি"}'),
                  onTap: () async {
                    await Navigator.push(context,
                        MaterialPageRoute(builder: (_) => DocumentScreen(store: widget.store, documentId: d.id)));
                    setState(() {});
                  },
                ),
            ]),
    );
  }
}
