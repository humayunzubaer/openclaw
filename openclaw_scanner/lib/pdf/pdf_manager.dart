import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;
import '../data/db/app_database.dart';
import '../export/export_source.dart';
import '../export/jpg_exporter.dart';
import 'pdf_service.dart';

class PdfManager {
  PdfManager(this._db, this._pdf, this._jpg, this._exportsDir);
  final AppDatabase _db;
  final PdfService _pdf;
  final JpgExporter _jpg;
  final Directory _exportsDir;

  /// Bengali edit baked image থেকে PDF।
  Future<String> exportDocumentPdf(String documentId, {bool compress = true}) async {
    final pages = await ExportSource(_db).collect(documentId);
    final jpgs = await _jpg.export(pages, quality: 92);
    var out = p.join(_exportsDir.path, '$documentId.pdf');
    await _pdf.fromImages(jpgs, out);
    if (compress) {
      final small = p.join(_exportsDir.path, '${documentId}_compressed.pdf');
      out = await _pdf.compress(out, small, dpi: 200, quality: 72);
    }
    return out;
  }

  /// Invisible Bengali OCR text layer সহ searchable PDF।
  Future<String> exportSearchablePdf(String documentId,
      {required String bengaliFontPath, bool compress = true}) async {
    final pages = await ExportSource(_db).collect(documentId);
    final jpgs = await _jpg.export(pages, quality: 92);
    final imagePdf = p.join(_exportsDir.path, '$documentId.pdf');
    await _pdf.fromImages(jpgs, imagePdf);

    final placements = <Map<String, dynamic>>[];
    for (var i = 0; i < pages.length; i++) {
      final pe = pages[i];
      final items = <Map<String, dynamic>>[];
      final edited = pe.page.editState['textEdits'] != null;
      if (edited) {
        for (final b in pe.blocks) {
          final lines = b.text.split('\n');
          final lh = b.rectN.height / lines.length;
          for (var li = 0; li < lines.length; li++) {
            if (lines[li].trim().isEmpty) continue;
            items.add({'text': lines[li], 'x': b.rectN.left, 'y': b.rectN.top + li * lh, 'w': b.rectN.width, 'h': lh});
          }
        }
      } else {
        for (final w in await _db.getOcrBlocks(pe.page.id)) {
          items.add({'text': w.text, 'x': w.x, 'y': w.y, 'w': w.w, 'h': w.h});
        }
      }
      placements.add({'page': i, 'items': items});
    }

    var out = p.join(_exportsDir.path, '${documentId}_searchable.pdf');
    await _pdf.addTextLayer(imagePdf, out, bengaliFontPath, jsonEncode(placements));
    if (compress) {
      final small = p.join(_exportsDir.path, '${documentId}_searchable_min.pdf');
      out = await _pdf.compress(out, small, dpi: 200, quality: 72);
    }
    return out;
  }

  Future<String> extractPages(String pdfPath, List<int> zeroBasedPages) =>
      _pdf.extract(pdfPath, zeroBasedPages, p.setExtension(pdfPath, '.extract.pdf'));

  Future<String> combine(List<String> pdfPaths, String name) =>
      _pdf.combine(pdfPaths, p.join(_exportsDir.path, name));

  Future<String> compress(String pdfPath, {int dpi = 200, int quality = 72}) =>
      _pdf.compress(pdfPath, p.setExtension(pdfPath, '.min.pdf'), dpi: dpi, quality: quality);
}
