import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;

/// প্রতিটা শট নেওয়ার পর দেখানো হয় — Retake (আবার তুলুন) / Rotate (ঘোরান) /
/// Keep (রাখুন)। ভুল ছবি সাথে সাথেই ঠিক করা যায়, batch শেষ হওয়া পর্যন্ত অপেক্ষা
/// করতে হয় না।
class CaptureReviewScreen extends StatefulWidget {
  const CaptureReviewScreen({
    super.key,
    required this.imagePath,
    required this.pageLabel,
    required this.onRetake,
    required this.onKeep,
  });

  final String imagePath;
  final String pageLabel; // যেমন "পেজ পস঳"
  final VoidCallback onRetake;
  final void Function(int rotationDegrees) onKeep;

  @override
  State<CaptureReviewScreen> createState() => _CaptureReviewScreenState();
}

class _CaptureReviewScreenState extends State<CaptureReviewScreen> {
  int _rotation = 0;

  void _rotate() => setState(() => _rotation = (_rotation + 90) % 360);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                '${widget.pageLabel} — রিভিউ করুন',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
            Expanded(
              child: Center(
                child: RotatedBox(
                  quarterTurns: _rotation ~/ 90,
                  child: Image.file(File(widget.imagePath)),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _rotate,
                      icon: const Icon(Icons.rotate_right),
                      label: const Text('ঘোরান'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: widget.onRetake,
                      icon: const Icon(Icons.replay),
                      label: const Text('রিটেক'),
                      style: OutlinedButton.styleFrom(foregroundColor: Colors.redAccent),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () => widget.onKeep(_rotation),
                      icon: const Icon(Icons.check),
                      label: const Text('রাখুন'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// rotate করা হলে সেই rotation স্থায়ীভাবে ছবিতে বেক করে একটা নতুন ফাইল হিসেবে
/// সেভ করে — যাতে পরে export/thumbnail-এ প্রতিবার আলাদা করে rotation হিসাব
/// করতে না হয়।
Future<String> bakeRotation(String srcPath, int degrees) async {
  if (degrees == 0) return srcPath;
  final bytes = await File(srcPath).readAsBytes();
  final image = img.decodeImage(bytes);
  if (image == null) return srcPath;
  final rotated = img.copyRotate(image, angle: degrees);
  final outPath = srcPath.replaceFirst('.jpg', '_r$degrees.jpg');
  await File(outPath).writeAsBytes(img.encodeJpg(rotated, quality: 92));
  return outPath;
}
