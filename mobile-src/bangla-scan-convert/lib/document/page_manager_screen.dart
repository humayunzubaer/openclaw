import 'dart:io';
import 'package:flutter/material.dart';
import '../doc_store.dart';
import '../models.dart';

/// ডকুমেন্টের মাঝখান থেকে এক বা একাধিক পাতা মুছে ফেলা, অথবা নির্বাচিত পাতাগুলোকে
/// একটা নতুন আলাদা ডকুমেন্টে "এক্সট্র্যাক্ট" করা। যেহেতু ডকুমেন্ট এমনিতেই page-image
/// list হিসেবে থাকে, এখানে কোনো PDF-parsing library লাগেনি — শুধু list ম্যানিপুলেশন,
/// আর export (Word/Excel/PDF) পরে এই বদলানো page list থেকেই হবে।
///
/// থাম্বনেইল-গুলো `cacheWidth` দিয়ে ছোট রেজোলুশনে decode হয় — grid smooth রাখতে।
class PageManagerScreen extends StatefulWidget {
  const PageManagerScreen({super.key, required this.store, required this.documentId});
  final DocStore store;
  final String documentId;

  @override
  State<PageManagerScreen> createState() => _PageManagerScreenState();
}

class _PageManagerScreenState extends State<PageManagerScreen> {
  final Set<String> _selected = {};

  ScanDocument get _doc => widget.store.byId(widget.documentId)!;

  Future<void> _deleteSelected() async {
    if (_selected.isEmpty) return;
    await widget.store.deletePages(widget.documentId, _selected);
    setState(() => _selected.clear());
  }

  Future<void> _extractSelected() async {
    if (_selected.isEmpty) return;
    // MVP: নির্বাচিত পাতাগুলো একটা নতুন ScanDocument হিসেবে আলাদা করে দেওয়া হয়;
    // মূল ডকুমেন্ট থেকে বাদ দেওয়া হয় না (extract = কপি, delete = সরানো)।
    final doc = _doc;
    final extractedPages = doc.pages.where((p) => _selected.contains(p.id)).toList();
    final newDoc = ScanDocument(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: '${doc.title} — Extract',
      pages: extractedPages,
      createdAt: DateTime.now(),
      docKind: doc.docKind,
    );
    await widget.store.addDocument(newDoc);
    setState(() => _selected.clear());
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('"${newDoc.title}" নামে নতুন ডকুমেন্ট তৈরি হয়েছে')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final doc = _doc;
    return Scaffold(
      appBar: AppBar(
        title: const Text('পেজ ম্যানেজ করুন'),
        actions: [
          if (_selected.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Center(child: Text('${_selected.length}টি নির্বাচিত')),
            ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              'পেজে চেপে নির্বাচন করুন — মাঝখানের যেকোনো পেজ মুছে ফেলা বা আলাদা করে বের করা যাবে।',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3, crossAxisSpacing: 8, mainAxisSpacing: 8,
              ),
              itemCount: doc.pages.length,
              itemBuilder: (context, i) {
                final page = doc.pages[i];
                final isSelected = _selected.contains(page.id);
                return GestureDetector(
                  onTap: () => setState(() {
                    isSelected ? _selected.remove(page.id) : _selected.add(page.id);
                  }),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      // cacheWidth: full-res ছবি না decode করে ছোট সাইজেই লোড — grid smooth থাকে
                      if (page.hasImage)
                        Image.file(File(page.imagePath!), fit: BoxFit.cover, cacheWidth: 200)
                      else
                        Container(color: Colors.black12, child: const Icon(Icons.description_outlined)),
                      if (isSelected)
                        Container(
                          decoration: BoxDecoration(
                            border: Border.all(color: Theme.of(context).colorScheme.primary, width: 3),
                          ),
                          child: const Align(
                            alignment: Alignment.topRight,
                            child: Icon(Icons.check_circle, color: Colors.amber),
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    onPressed: _selected.isEmpty ? null : _deleteSelected,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('নির্বাচিত মুছুন'),
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _selected.isEmpty ? null : _extractSelected,
                    icon: const Icon(Icons.call_split),
                    label: const Text('নতুন ডকুমেন্টে এক্সট্র্যাক্ট'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
