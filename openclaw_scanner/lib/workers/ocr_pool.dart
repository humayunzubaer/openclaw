import 'dart:async';
import 'dart:io';
import 'dart:isolate';
import 'dart:math';
import 'package:drift/isolate.dart';

import '../data/db/app_database.dart';
import 'messages.dart';
import 'ocr_worker.dart';

class OcrPool {
  OcrPool._(this._db, this._driftIsolate, this._tessdataDir, this.concurrency);

  final AppDatabase _db;
  final DriftIsolate _driftIsolate;
  final String _tessdataDir;
  final int concurrency;
  final _workers = <int, SendPort>{};
  final _stopped = <int>{};
  Completer<void>? _drained;

  /// একই DriftIsolate share করে (single writer)।
  static Future<OcrPool> attach({
    required AppDatabase mainDb,
    required DriftIsolate driftIsolate,
    required String tessdataDir,
  }) async {
    final pool = OcrPool._(mainDb, driftIsolate, tessdataDir,
        max(1, Platform.numberOfProcessors - 1));
    await pool._spawn();
    return pool;
  }

  Future<void> enqueueDocument(String documentId) async {
    await _db.enqueueDocumentOcr(documentId);
    _wakeAll();
  }

  Future<void> cancelDocument(String documentId) => _db.cancelDocumentOcr(documentId);
  Stream<double> watchProgress(String documentId) => _db.watchDocumentOcrProgress(documentId);

  void _wakeAll() { for (final p in _workers.values) p.send('wake'); }

  Future<void> _spawn() async {
    final ready = ReceivePort();
    final gotAll = Completer<void>();
    ready.listen((m) {
      if (m is WorkerReady) {
        _workers[m.id] = m.control;
        if (_workers.length == concurrency) gotAll.complete();
      } else if (m is WorkerStopped) {
        _stopped.add(m.id);
        if (_stopped.length == concurrency) _drained?.complete();
      }
    });
    for (var i = 0; i < concurrency; i++) {
      await Isolate.spawn(
        ocrWorkerMain,
        OcrWorkerConfig(
          driftIsolate: _driftIsolate,
          toPool: ready.sendPort,
          tessdataDir: _tessdataDir,
          scratchBytes: 64 << 20,
          workerId: i,
        ),
        debugName: 'ocr-worker-$i',
      );
    }
    await gotAll.future;
  }

  Future<void> shutdown() async {
    _drained = Completer<void>();
    for (final p in _workers.values) p.send('stop');
    await _drained!.future.timeout(const Duration(seconds: 5), onTimeout: () {});
  }
}
