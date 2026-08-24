import 'dart:convert';
import 'package:drift/drift.dart';

/// Capture mode — কোন OpenCV pre-pipeline চলবে তা ঠিক করে।
enum CaptureMode { document, book, businessCard, idCard }

/// প্রতি-page OCR lifecycle (queue state machine-এর সাথে মেলে)।
enum PageOcrState { none, queued, running, done, failed, skipped }

/// Document-level rollup।
enum DocOcrStatus { none, partial, complete }

/// Text block কোথা থেকে এলো। Phase-1 এ typed; Phase-2 Bengali ICR handwritten
/// লিখবে — কোনো schema change ছাড়াই।
enum TextSource { typed, handwritten }

enum JobType { ocr, magicErase, export, compress }
enum JobState { queued, running, done, failed, cancelled }

/// JSON map store করে (edit_state ops, resumable checkpoint)।
class JsonMapConverter extends TypeConverter<Map<String, dynamic>, String> {
  const JsonMapConverter();
  @override
  Map<String, dynamic> fromSql(String fromDb) =>
      fromDb.isEmpty ? const {} : jsonDecode(fromDb) as Map<String, dynamic>;
  @override
  String toSql(Map<String, dynamic> value) => jsonEncode(value);
}
