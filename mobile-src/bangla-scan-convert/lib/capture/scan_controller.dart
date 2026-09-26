import 'package:cunning_document_scanner/cunning_document_scanner.dart';

/// প্রতিটা কল প্লাগিনের নিজস্ব single-shot ক্যামেরা UI খোলে (auto-crop সহ),
/// একটা ছবির path ফেরত দেয় — বা বাতিল করলে null।
class ScanController {
  Future<String?> captureOne() async {
    final paths = await CunningDocumentScanner.getPictures(noOfPages: 1) ?? [];
    return paths.isEmpty ? null : paths.first;
  }
}
