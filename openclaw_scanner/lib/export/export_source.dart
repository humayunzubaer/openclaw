import '../data/db/app_database.dart';
import '../editor/text/text_block_model.dart';
import '../editor/text/text_layout_builder.dart';

class PageExport {
  PageExport({required this.page, required this.blocks});
  final Page page;
  final List<EditableTextBlock> blocks; // edited overlay থাকলে সেটা, নাহলে OCR থেকে
}

class ExportSource {
  ExportSource(this._db);
  final AppDatabase _db;

  Future<List<PageExport>> collect(String documentId) async {
    final pages = await _db.pagesOfOrdered(documentId);
    return [
      for (final p in pages)
        PageExport(
          page: p,
          blocks: (p.editState['textEdits'] as List?)
                  ?.map((j) => EditableTextBlock.fromJson(j as Map<String, dynamic>))
                  .toList() ??
              TextLayoutBuilder.build(await _db.getOcrBlocks(p.id)),
        ),
    ];
  }
}
