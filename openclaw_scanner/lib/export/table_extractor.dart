import '../data/db/app_database.dart';

class TableExtractor {
  /// Word box থেকে rows × columns grid — column x-center gap দিয়ে detect।
  static List<List<String>> extract(List<OcrBlock> words, {double colGapN = 0.045}) {
    if (words.isEmpty) return const [];

    final byLine = <String, List<OcrBlock>>{};
    for (final w in words) {
      (byLine[w.lineId ?? (w.y * 100).round().toString()] ??= []).add(w);
    }
    final rows = byLine.values.toList()..sort((a, b) => a.first.y.compareTo(b.first.y));

    final centers = words.map((w) => w.x + w.w / 2).toList()..sort();
    final bands = <double>[];
    for (final c in centers) {
      if (bands.isEmpty || c - bands.last > colGapN) bands.add(c);
    }

    return [
      for (final row in rows)
        () {
          final cells = List.filled(bands.length, '');
          for (final w in row..sort((a, b) => a.x.compareTo(b.x))) {
            final cx = w.x + w.w / 2;
            var col = 0;
            for (var i = 1; i < bands.length; i++) {
              if ((cx - bands[i]).abs() < (cx - bands[col]).abs()) col = i;
            }
            cells[col] = cells[col].isEmpty ? w.text : '${cells[col]} ${w.text}';
          }
          return cells;
        }(),
    ];
  }
}
