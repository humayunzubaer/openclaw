import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import '../app/providers.dart';
import '../capture/scan_screen.dart';
import '../document/document_screen.dart';
import '../export/export_service.dart';

class LibraryScreen extends ConsumerWidget {
  const LibraryScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docs = ref.watch(documentsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('আমার ডকুমেন্ট')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () =>
            Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen())),
        icon: const Icon(Icons.add_a_photo),
        label: const Text('নতুন স্ক্যান'),
      ),
      body: docs.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (list) => list.isEmpty
            ? const Center(child: Text('এখনো কোনো ডকুমেন্ট নেই।\n"নতুন স্ক্যান" চাপুন।',
                textAlign: TextAlign.center))
            : ListView(children: [
                for (final d in list)
                  ListTile(
                    leading: const Icon(Icons.description),
                    title: Text(d.title),
                    subtitle: Text('${d.pageCount} পৃষ্ঠা · OCR: ${d.ocrStatus.name}'),
                    onTap: () => Navigator.push(context,
                        MaterialPageRoute(builder: (_) => DocumentScreen(documentId: d.id))),
                    trailing: PopupMenuButton<ExportFormat>(
                      onSelected: (fmt) async {
                        final s = await ref.read(appServicesProvider.future);
                        final files = await s.exportService.run(d.id, fmt);
                        await Share.shareXFiles([for (final f in files) XFile(f)]);
                      },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: ExportFormat.docx, child: Text('Word (.docx)')),
                        PopupMenuItem(value: ExportFormat.xlsx, child: Text('Excel (.xlsx)')),
                        PopupMenuItem(value: ExportFormat.jpg, child: Text('JPG')),
                      ],
                    ),
                  ),
              ]),
      ),
    );
  }
}
