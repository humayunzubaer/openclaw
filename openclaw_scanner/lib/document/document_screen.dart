import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/app_services.dart';
import '../app/providers.dart';
import '../data/db/app_database.dart';
import '../editor/text/in_scan_text_editor.dart';
import '../editor/text/text_block_model.dart';
import '../editor/text/text_layout_builder.dart';

class DocumentScreen extends ConsumerWidget {
  const DocumentScreen({super.key, required this.documentId});
  final String documentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final servicesAsync = ref.watch(appServicesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('পৃষ্ঠাসমূহ')),
      body: servicesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (services) => FutureBuilder<List<Page>>(
          future: services.db.pagesOfOrdered(documentId),
          builder: (context, snap) {
            final pages = snap.data ?? const [];
            if (pages.isEmpty) return const Center(child: CircularProgressIndicator());
            return GridView.count(
              crossAxisCount: 3,
              padding: const EdgeInsets.all(8),
              children: [
                for (final page in pages)
                  GestureDetector(
                    onTap: () => _openEditor(context, services, page),
                    child: Card(
                      child: page.thumbPath != null
                          ? Image.file(File(page.thumbPath!), fit: BoxFit.cover)
                          : const Icon(Icons.image),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  Future<void> _openEditor(BuildContext context, AppServices services, Page page) async {
    final saved = (page.editState['textEdits'] as List?)
        ?.map((j) => EditableTextBlock.fromJson(j as Map<String, dynamic>))
        .toList();
    final blocks = saved ?? TextLayoutBuilder.build(await services.db.getOcrBlocks(page.id));
    if (!context.mounted) return;
    await Navigator.push(context, MaterialPageRoute(
      builder: (_) => InScanTextEditor(
        imageFile: File(page.procPath ?? page.rawPath),
        imageWidthPx: page.width.toDouble(),
        imageHeightPx: page.height.toDouble(),
        blocks: blocks,
        onSave: (edited) =>
            services.db.saveTextEdits(page.id, [for (final b in edited) b.toJson()]),
      ),
    ));
  }
}
