import 'package:drift/drift.dart';

/// Enterprise status surface-এর জন্য live queue view।
class QueueStats {
  QueueStats(this.byTypeState);
  final Map<(String, String), int> byTypeState;

  int get queued => _sum('queued');
  int get running => _sum('running');
  int get failed => _sum('failed');
  int _sum(String state) =>
      byTypeState.entries.where((e) => e.key.$2 == state).fold(0, (a, e) => a + e.value);

  factory QueueStats.fromRows(List<QueryRow> rows) => QueueStats({
        for (final r in rows)
          (r.read<String>('type'), r.read<String>('state')): r.read<int>('n'),
      });
}
