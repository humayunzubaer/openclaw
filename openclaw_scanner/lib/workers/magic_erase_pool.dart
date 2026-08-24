import 'dart:async';
import 'dart:ffi';
import 'dart:io';
import 'dart:isolate';
import 'dart:math';
import 'package:drift/isolate.dart';
import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;

import '../data/db/app_database.dart';
import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';
import 'magic_erase_worker.dart';
import 'messages.dart';

class MagicErasePool {
  MagicErasePool._(this._db, this._driftIsolate, this._core, this._inpainterAddr, this.concurrency);

  final AppDatabase _db;
  final DriftIsolate _driftIsolate;
  final ScannerCore _core;
  final int _inpainterAddr;
  final int concurrency;
  final _workers = <int, SendPort>{};
  final _stopped = <int>{};
  Completer<void>? _drained;

  static Future<MagicErasePool> boot({
    required AppDatabase mainDb,
    required DriftIsolate driftIsolate,
    required String lamaModelPath,
  }) async {
    final core = ScannerCore.open();
    core.initDartApi(); // process-এ একবার, worker port post করার আগে

    final accel = switch (defaultTargetPlatform) {
      TargetPlatform.android => ScAccel.SC_NNAPI,
      TargetPlatform.iOS => ScAccel.SC_COREML,
      _ => ScAccel.SC_XNNPACK,
    };
    final inpainter = core.inpaintCreate(lamaModelPath, accel.value);

    final isAccel = accel == ScAccel.SC_NNAPI || accel == ScAccel.SC_COREML;
    final concurrency = isAccel ? 1 : min(2, max(1, Platform.numberOfProcessors - 1));

    final pool = MagicErasePool._(mainDb, driftIsolate, core, inpainter.address, concurrency);
    await pool._spawn();
    return pool;
  }

  Future<void> applyErase(
    String pageId, {
    required String maskPath,
    int tileSize = 512,
    int overlap = 64,
    String? outPath,
  }) async {
    await _db.enqueueMagicErase(pageId,
        maskPath: maskPath, tileSize: tileSize, overlap: overlap, outPath: outPath);
    for (final p in _workers.values) p.send('wake');
  }

  Stream<double> watchProgress(String pageId) => _db.watchEraseProgress(pageId);

  Future<void> _spawn() async {
    final ready = ReceivePort();
    final done = Completer<void>();
    ready.listen((m) {
      if (m is WorkerReady) {
        _workers[m.id] = m.control;
        if (_workers.length == concurrency) done.complete();
      } else if (m is WorkerStopped) {
        _stopped.add(m.id);
        if (_stopped.length == concurrency) _drained?.complete();
      }
    });
    for (var i = 0; i < concurrency; i++) {
      await Isolate.spawn(
        magicEraseWorkerMain,
        MagicEraseConfig(
          driftIsolate: _driftIsolate,
          toPool: ready.sendPort,
          inpainterAddr: _inpainterAddr,
          scratchBytes: 96 << 20,
          workerId: i,
        ),
        debugName: 'erase-worker-$i',
      );
    }
    await done.future;
  }

  Future<void> shutdown() async {
    _drained = Completer<void>();
    for (final p in _workers.values) p.send('stop');
    await _drained!.future.timeout(const Duration(seconds: 5), onTimeout: () {});
    _core.inpaintDestroy(Pointer<ScInpainter>.fromAddress(_inpainterAddr)); // একবার free
  }
}
