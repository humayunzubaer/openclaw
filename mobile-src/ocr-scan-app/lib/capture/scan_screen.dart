import 'dart:io';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../doc_store.dart';
import '../models.dart';
import '../document/document_screen.dart';
import 'capture_review_screen.dart';
import 'scan_controller.dart';

const _maxPages = 100;

/// একবারে ১টা shot → capture → Retake/Rotate/Keep রিভিউ → gallery-তে যোগ →
/// পরের shot। ১০০ পাতা পর্যন্ত, কোনো ল্যাগ ছাড়াই।
class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key, required this.store});
  final DocStore store;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _controller = ScanController();
  final List<ScanPage> _pages = [];
  bool _busy = false;

  Future<void> _captureLoop() async {
    if (_pages.length >= _maxPages) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('সর্বোচ্চ ১০০ পাতা — এখন Done চাপুন')));
      return;
    }
    await _captureOne(label: 'পেজ ${_pages.length + 1}');
  }

  Future<void> _captureOne({required String label}) async {
    setState(() => _busy = true);
    final rawPath = await _controller.captureOne();
    if (mounted) setState(() => _busy = false);
    if (rawPath == null || !mounted) return;

    final result = await Navigator.push<int?>(
      context,
      MaterialPageRoute(
        builder: (_) => CaptureReviewScreen(
          imagePath: rawPath,
          pageLabel: label,
          onRetake: () => Navigator.pop(context),
          onKeep: (rotation) => Navigator.pop(context, rotation),
        ),
      ),
    );
    if (!mounted) return;

    if (result == null) {
      await _captureOne(label: label); // retake — একই ধাপ আবার
      return;
    }
    final finalPath = result == 0 ? rawPath : await bakeRotation(rawPath, result);
    setState(() => _pages.add(ScanPage(id: const Uuid().v4(), imagePath: finalPath)));
  }

  Future<void> _finish() async {
    if (_pages.isEmpty) {
      if (mounted) Navigator.pop(context);
      return;
    }
    final doc = ScanDocument(
      id: const Uuid().v4(),
      title: 'স্ক্যান ${DateTime.now().toString().substring(0, 16)}',
      pages: _pages,
      createdAt: DateTime.now(),
    );
    await widget.store.addDocument(doc);
    if (mounted) {
      Navigator.pushReplacement(context,
          MaterialPageRoute(builder: (_) => DocumentScreen(store: widget.store, documentId: doc.id)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('নতুন স্ক্যান (${_pages.length} পাতা)')),
      body: Column(
        children: [
          Expanded(
            child: _pages.isEmpty
                ? const Center(child: Text('ক্যাপচার শুরু করতে নিচের বাটন চাপুন'))
                : GridView.builder(
                    padding: const EdgeInsets.all(8),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 4),
                    itemCount: _pages.length,
                    // cacheWidth: grid-এ full-res ছবি নয়, ছোট decode — স্মুথ থাকে
                    itemBuilder: (context, i) => Padding(
                      padding: const EdgeInsets.all(4),
                      child: Image.file(File(_pages[i].imagePath), fit: BoxFit.cover, cacheWidth: 150),
                    ),
                  ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _captureLoop,
                    icon: const Icon(Icons.camera_alt),
                    label: Text(_busy ? '...' : 'ক্যাপচার করুন'),
                  ),
                ),
                if (_pages.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  OutlinedButton(onPressed: _finish, child: const Text('শেষ')),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
