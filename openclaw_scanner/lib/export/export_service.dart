import 'dart:io';
import 'dart:isolate';
import 'package:path/path.dart' as p;
import '../data/db/app_database.dart';
import 'docx_writer.dart';
import 'export_source.dart';
import 'jpg_exporter.dart';
import 'table_extractor.dart';
import 'xlsx_writer.dart';

enum ExportFormat { docx, xlsx, jpg }

class ExportService {
  ExportService(this._db, this._exportsDir);
  final AppDatabase _db;
  final Directory _exportsDir;

  Future<List<String>> run(String documentId, ExportFormat format) async {
    final pages = await ExportSource(_db).collect(documentId);
    switch (format) {
      case ExportFormat.docx:
        final bytes = await Isolate.run(() => DocxWriter().build(pages));
        return [await _write('$documentId.docx', bytes)];
      case ExportFormat.xlsx:
        final grids = <List<List<String>>>[];
        for (final pe in pages) {
          grids.add(TableExtractor.extract(await _db.getOcrBlocks(pe.page.id)));
        }
        final flat = grids.expand((g) => g).toList();
        final bytes = await Isolate.run(() => XlsxWriter().build(flat));
        return [await _write('$documentId.xlsx', bytes)];
      case ExportFormat.jpg:
        return JpgExporter(_exportsDir).export(pages);
    }
  }

  Future<String> _write(String name, List<int> bytes) async {
    final f = File(p.join(_exportsDir.path, name));
    await f.writeAsBytes(bytes, flush: true);
    return f.path;
  }
}
