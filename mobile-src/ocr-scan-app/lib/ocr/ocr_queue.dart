import 'dart:async';
import '../doc_store.dart';
import '../models.dart';
import 'ocr_engine.dart';

/// ১০০-পাতা পর্যন্ত ব্যাচ OCR — একবারে এক পাতা প্রসেস করে (মেমোরিতে কখনো ১০০টা
/// ছবি একসাথে নয়), প্রতিটার পর progress জানায়, ফলাফল সাথে সাথে DocStore-এ সেভ
/// হয় — অ্যাপ মাঝপথে বন্ধ হলে ইতিমধ্যে-হওয়া পাতা হারায় না, বাকিগুলো আবার
/// চালালেই চলতে থাকে (resume)।
///
/// **UI ফ্রিজ হবে না কেন:** প্রতিটা `_engine.recognize()` কল একটা `await`-করা
/// Future — এই await-এর সময় Dart-এর event loop অন্য কাজ (UI rebuild, animation
/// frame, user tap) প্রসেস করতে থাকে। তাই progress bar smoothly আপডেট হয়।
class OcrQueue {
  OcrQueue(this._store, this._engine);

  final DocStore _store;
  final OcrEngine _engine;

  /// [document]-এর যেসব পাতার `ocrDone == false`, শুধু সেগুলোই প্রসেস করে —
  /// তাই থেমে যাওয়া ব্যাচ আবার চালালে বাকি অংশ থেকেই চলবে।
  Future<void> runDocument(
    ScanDocument document, {
    void Function(int done, int total)? onProgress,
  }) async {
    final pending = document.pages.where((p) => !p.ocrDone).toList();
    final total = pending.length;
    var done = 0;

    for (final page in pending) {
      final text = await _engine.recognize(page.imagePath);
      await _store.updatePageOcr(document.id, page.id, text);
      done++;
      onProgress?.call(done, total);
    }
  }
}
