import 'dart:convert';
import 'dart:typed_data';
import 'package:archive/archive.dart';

List<int> utf8Bytes(String s) => const Utf8Encoder().convert(s);

Uint8List zipOoxml(Map<String, String> files) {
  final archive = Archive();
  files.forEach((name, xml) {
    final bytes = utf8Bytes(xml);
    archive.addFile(ArchiveFile(name, bytes.length, bytes));
  });
  return Uint8List.fromList(ZipEncoder().encode(archive)!);
}

String xmlEscape(String s) =>
    s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
