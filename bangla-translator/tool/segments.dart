// Prints each stdin line as JSON font runs: [[isBijoy, text], ...].
// Usage: dart run tool/segments.dart < text.txt
import 'dart:convert';
import 'dart:io';

import 'package:bangla_translator/bijoy/unicode_to_bijoy.dart';

Future<void> main() async {
  final text = await stdin.transform(utf8.decoder).join();
  for (final line in const LineSplitter().convert(text)) {
    final runs = [
      for (final s in convertToSegments(line)) [s.isBijoy, s.text],
    ];
    stdout.writeln(jsonEncode(runs));
  }
}
