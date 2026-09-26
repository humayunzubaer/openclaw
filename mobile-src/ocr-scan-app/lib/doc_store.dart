import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'models.dart';

/// সব ডকুমেন্টের তালিকা একটা সাধারণ JSON ফাইলে — ভারী database লাগে না।
class DocStore {
  DocStore._(this._file, this._docs);

  final File _file;
  final List<ScanDocument> _docs;

  List<ScanDocument> get documents => List.unmodifiable(_docs);

  static Future<Directory> appDir() async {
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory(p.join(base.path, 'ocr_scan_app'));
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  static Future<DocStore> load() async {
    final dir = await appDir();
    final file = File(p.join(dir.path, 'documents.json'));
    List<ScanDocument> docs = [];
    if (await file.exists()) {
      final raw = await file.readAsString();
      if (raw.trim().isNotEmpty) {
        final list = jsonDecode(raw) as List;
        docs = list
            .map((d) => ScanDocument.fromJson(d as Map<String, dynamic>))
            .toList();
      }
    }
    return DocStore._(file, docs);
  }

  Future<void> _save() async {
    final list = _docs.map((d) => d.toJson()).toList();
    await _file.writeAsString(jsonEncode(list), flush: true);
  }

  Future<void> addDocument(ScanDocument doc) async {
    _docs.add(doc);
    await _save();
  }

  Future<void> updatePageOcr(String docId, String pageId, String ocrText) async {
    final page = _findPage(docId, pageId);
    page.ocrText = ocrText;
    page.ocrDone = true;
    await _save();
  }

  Future<void> replacePageImage(String docId, String pageId, String newPath) async {
    final page = _findPage(docId, pageId);
    page.imagePath = newPath;
    page.rotationDegrees = 0; // নতুন ছবি ধরে নিলে rotation রিসেট
    page.ocrDone = false; // retake করলে আগের OCR আর প্রযোজ্য নয়
    page.ocrText = null;
    await _save();
  }

  ScanPage _findPage(String docId, String pageId) {
    final doc = byId(docId)!;
    return doc.pages.firstWhere((p) => p.id == pageId);
  }

  ScanDocument? byId(String id) {
    for (final d in _docs) {
      if (d.id == id) return d;
    }
    return null;
  }
}
