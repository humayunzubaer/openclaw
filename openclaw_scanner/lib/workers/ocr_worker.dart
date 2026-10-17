import 'dart:async';
import 'dart:ffi';
import 'dart:isolate';
import 'package:drift/isolate.dart';
import 'package:ffi/ffi.dart';

import '../data/db/app_database.dart';
import '../data/db/converters.dart';
import '../native/ocr_engine.dart';
import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';
import 'messages.dart';

class OcrWorkerConfig {
  const OcrWorkerConfig({
    required this.driftIsolate,
    required this.toPool,
    required this.tessdataDir,
    required this.scratchBytes,
    required this.workerId,
  });
  final DriftIsolate driftIsolate;
  final SendPort toPool;
  final String tessdataDir;
  final int scratchBytes;
  final int workerId;
}

/// Long-lived worker: native resource একবার setup, তারপর loop।
Future<void> ocrWorkerMain(OcrWorkerConfig cfg) async {
  final db = AppDatabase(await cfg.driftIsolate.connect());
  final core = ScannerCore.open();
  final ocr = NativeOcrEngine(core, tessdataDir: cfg.tessdataDir, lang: 'ben');
  final scratch = core.scratchCreate(cfg.scratchBytes);

  final control = ReceivePort();
  var running = true;
  Completer<void>? idle;
  control.listen((m) {
    if (m == 'stop') { running = false; idle?.complete(); }
    else if (m == 'wake') { idle?.complete(); }
  });
  cfg.toPool.send(WorkerReady(cfg.workerId, control.sendPort));

  try {
    while (running) {
      final job = await db.claimNextJob({JobType.ocr});
      if (job == null) {
        idle = Completer<void>();
        await idle!.future.timeout(const Duration(seconds: 5), onTimeout: () {});
        idle = null;
        continue;
      }
      await _processOcrJob(db, core, ocr, scratch, job);
    }
  } finally {
    core.scratchDestroy(scratch);
    ocr.dispose();
    await db.close();
    control.close();
    cfg.toPool.send(WorkerStopped(cfg.workerId));
  }
}

Future<void> _processOcrJob(AppDatabase db, ScannerCore core, NativeOcrEngine ocr,
    Pointer<ScScratch> scratch, Job job) async {
  final page = await db.getPageById(job.targetId);
  if (page == null || page.ocrState == PageOcrState.skipped) {
    await db.markJobDone(job.id);
    return;
  }
  final path = page.procPath ?? page.rawPath;
  final view = calloc<ScImage>();
  final cPath = path.toNativeUtf8();
  try {
    core.scratchReset(scratch);
    core.b.sc_scratch_load_file(scratch, cPath.cast(), view);
    await db.updateJobProgress(job.id, 0.25);

    core.b.sc_scratch_preprocess_for_ocr(scratch, view);
    await db.updateJobProgress(job.id, 0.50);

    final rows = ocr.recognize(view, page.id); // TextSource.typed
    await db.updateJobProgress(job.id, 0.85);

    await db.writeOcrResult(job.id, page.id, rows);
    await db.refreshDocOcrStatus(page.documentId);
  } catch (e) {
    await db.handleOcrFailure(job, page.id, e);
  } finally {
    core.scratchReset(scratch);
    calloc.free(view);
    calloc.free(cPath);
  }
}
