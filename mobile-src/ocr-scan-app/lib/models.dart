/// সহজ, in-memory + local-file ভিত্তিক ডেটা মডেল — শুধু OCR অ্যাপের জন্য দরকারি অংশটুকু।

enum SourceKind { camera, importedImage }

class ScanPage {
  ScanPage({
    required this.id,
    required this.imagePath,
    this.ocrText,
    this.ocrDone = false,
    this.rotationDegrees = 0,
    this.source = SourceKind.camera,
  });

  final String id;
  String imagePath;
  String? ocrText;
  bool ocrDone;
  int rotationDegrees;
  SourceKind source;

  Map<String, dynamic> toJson() => {
        'id': id,
        'imagePath': imagePath,
        'ocrText': ocrText,
        'ocrDone': ocrDone,
        'rotationDegrees': rotationDegrees,
        'source': source.name,
      };

  factory ScanPage.fromJson(Map<String, dynamic> j) => ScanPage(
        id: j['id'] as String,
        imagePath: j['imagePath'] as String,
        ocrText: j['ocrText'] as String?,
        ocrDone: j['ocrDone'] as bool? ?? false,
        rotationDegrees: j['rotationDegrees'] as int? ?? 0,
        source: SourceKind.values.byName(j['source'] as String? ?? 'camera'),
      );
}

class ScanDocument {
  ScanDocument({
    required this.id,
    required this.title,
    required this.pages,
    required this.createdAt,
  });

  final String id;
  String title;
  final List<ScanPage> pages;
  final DateTime createdAt;

  bool get ocrComplete => pages.isNotEmpty && pages.every((p) => p.ocrDone);

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'pages': pages.map((p) => p.toJson()).toList(),
        'createdAt': createdAt.millisecondsSinceEpoch,
      };

  factory ScanDocument.fromJson(Map<String, dynamic> j) => ScanDocument(
        id: j['id'] as String,
        title: j['title'] as String,
        pages: (j['pages'] as List)
            .map((p) => ScanPage.fromJson(p as Map<String, dynamic>))
            .toList(),
        createdAt: DateTime.fromMillisecondsSinceEpoch(j['createdAt'] as int),
      );
}
