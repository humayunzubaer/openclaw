// Prints `word<TAB>bijoy` for every whitespace-separated word on stdin.
// Usage: dart run tool/convert.dart < words.txt
import 'dart:convert';
import 'dart:io';

import 'package:bangla_translator/bijoy/unicode_to_bijoy.dart';

Future<void> main() async {
  final text = await stdin.transform(utf8.decoder).join();
  for (final word in text.split(RegExp(r'\s+')).where((w) => w.isNotEmpty)) {
    stdout.writeln('$word\t${unicodeToBijoy(word)}');
  }
}
