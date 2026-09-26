import 'package:flutter_tesseract_ocr/flutter_tesseract_ocr.dart';

/// ready-made Tesseract প্লাগিন wrap করা — একটা ছবি → বাংলা টেক্সট।
/// প্লাগিনটা ভেতরে-ভেতরে native (Android-এর নিজস্ব) থ্রেডে OCR চালায় এবং একটা
/// Future রিটার্ন করে — তাই এখানে `await` করলেও Flutter-এর UI thread আটকায় না,
/// ফ্রেম রেন্ডারিং চলতেই থাকে (এটাই "ল্যাগ না হওয়া"-র মূল ভিত্তি)।
class OcrEngine {
  Future<String> recognize(String imagePath) async {
    try {
      final text = await FlutterTesseractOcr.extractText(
        imagePath,
        language: 'ben',
        args: {
          'psm': '4', // single column, variable size — স্ক্যান করা পাতার জন্য ভালো ডিফল্ট
          'preserve_interword_spaces': '1',
        },
      );
      return text.trim();
    } catch (_) {
      return ''; // ব্যর্থ পাতা — queue এটা এড়িয়ে পরেরটায় যাবে
    }
  }
}
