/// সহজ, in-memory + local-file ভিত্তিক ডেটা মডেল — ভারী database লাগে না MVP-তে।

enum CaptureKind { document, idCardFront, idCardBack }
enum SourceKind { camera, importedDocx, importedXlsx, importedImage }

class ScanPage {
  ScanPage({
    required this.id,
    this.imagePath, // ক্যামেরা/ছবি থেকে হলে path; Word/Excel থেকে সরাসরি এলে null
    this.ocrText,
    this.ocrDone = false,
    this.rotationDegrees = 0,
    this.kind = CaptureKind.document,
    this.source = SourceKind.camera,
  });

  final String id;
  String? imagePath;
  String? ocrText;
  bool ocrDone;
  int rotationDegrees;
  CaptureKind kind;
  SourceKind source;

  /// Word/Excel থেকে import করা পাতায় ছবি থাকে না — UI-তে thumbnail-এর বদলে
  /// টেক্সট-আইকন দেখাতে এটা ব্যবহার হয়।
  bool get hasImage => imagePath != null && imagePath!.isNotEmpty;

  Map<String, dynamic> toJson() => {
        'id': id,
        'imagePath': imagePath,
        'ocrText': ocrText,
        'ocrDone': ocrDone,
        'rotationDegrees': rotationDegrees,
        'kind': kind.name,
        'source': source.name,
      };

  factory ScanPage.fromJson(Map<String, dynamic> j) => ScanPage(
        id: j['id'] as String,
        imagePath: j['imagePath'] as String?,
        ocrText: j['ocrText'] as String?,
        ocrDone: j['ocrDone'] as bool? ?? false,
        rotationDegrees: j['rotationDegrees'] as int? ?? 0,
        kind: CaptureKind.values.byName(j['kind'] as String? ?? 'document'),
        source: SourceKind.values.byName(j['source'] as String? ?? 'camera'),
      );
}

enum DocumentKind { document, idCard, imported }

class ScanDocument {
  ScanDocument({
    required this.id,
    required this.title,
    required this.pages,
    required this.createdAt,
    this.docKind = DocumentKind.document,
  });

  final String id;
  String title;
  final List<ScanPage> pages;
  final DateTime createdAt;
  final DocumentKind docKind;

  bool get ocrComplete => pages.isNotEmpty && pages.every((p) => p.ocrDone);

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'pages': pages.map((p) => p.toJson()).toList(),
        'createdAt': createdAt.millisecondsSinceEpoch,
        'docKind': docKind.name,
      };

  factory ScanDocument.fromJson(Map<String, dynamic> j) => ScanDocument(
        id: j['id'] as String,
        title: j['title'] as String,
        pages: (j['pages'] as List)
            .map((p) => ScanPage.fromJson(p as Map<String, dynamic>))
            .toList(),
        createdAt: DateTime.fromMillisecondsSinceEpoch(j['createdAt'] as int),
        docKind: DocumentKind.values.byName(j['docKind'] as String? ?? 'document'),
      );
}
