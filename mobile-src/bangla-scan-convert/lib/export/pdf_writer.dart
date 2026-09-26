import 'dart:io';
import 'dart:typed_data';
import 'package:pdf/widgets.dart' as pw;
import '../models.dart';

/// প্রতিটা পাতা image হিসেবে বসে (rotation প্রযোগ করে) — Word/Excel-ই আসল
/// সম্পাদনাযোগ্য টেক্সট দেয়; এই PDF মূলত visual/archival কপি।
///
/// ⚠️ সৎ স্কোপ-নোট: Word/Excel থেকে import করা পাতায় কোনো ছবি থাকে না (সরাসরি
/// টেক্সট)। এই লেখাকে PDF পাতায় বসাতে একটা text-layout renderer লাগবে —
/// সেটা এখনো বানানো হয়নি, তাই এখন এমন পাতা PDF export-এ বাদ পড়ে যায় (crash
/// করে না)। ছবি-ভিত্তিক স্ক্যান করা ডকুমেন্টের জন্য এটা সম্পূর্ণ কাজ করে।
class PdfWriter {
  Future<Uint8List> build(ScanDocument document) async {
    final doc = pw.Document();
    for (final page in document.pages) {
      if (!page.hasImage) continue; // TODO: imported text-only পাতার জন্য text-layout PDF page
      final bytes = await File(page.imagePath!).readAsBytes();
      final image = pw.MemoryImage(bytes);
      final turns = (page.rotationDegrees ~/ 90) % 4;
      doc.addPage(
        pw.Page(
          build: (context) => pw.Center(
            child: pw.Transform.rotateBox(
              angle: turns * -1.5707963267948966, // ৯০° এককে (radians), ঘড়ির কাঁটার দিকে
              child: pw.Image(image, fit: pw.BoxFit.contain),
            ),
          ),
        ),
      );
    }
    return doc.save();
  }
}
