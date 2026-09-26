import 'dart:async';
import 'dart:ffi';
import 'dart:isolate';
import 'package:drift/isolate.dart';
import 'package:ffi/ffi.dart';

import '../data/db/app_database.dart';
import '../data/db/converters.dart';
import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';
import 'messages.dart';

const int kMsgProgress = 1, kMsgDone = 2, kMsgError = 3;

class MagicEraseConfig {
  const MagicEraseConfig({
    required this.driftIsolate,
    required this.toPool,
    required this.inpainterAddr, // shared LaMa session address
    required this.scratchBytes,
    required this.workerId,
  });
  final DriftIsolate driftIsolate;
  final SendPort toPool;
  final int inpainterAddr;
  final int scratchBytes;
  final int workerId;
}

Future<void> magicEraseWorkerMain(MagicEraseConfig cfg) async {
  final db = AppDatabase(await cfg.driftIsolate.connect());
  final core = ScannerCore.open();
  final inpainter = Pointer<ScInpainter>.fromAddress(cfg.inpainterAddr); // shared
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
      final job = await db.claimNextJob({JobType.magicErase});
      if (job == null) {
        idle = Completer<void>();
        await idle!.future.timeout(const Duration(seconds: 5), onTimeout: () {});
        idle = null;
        continue;
      }
      await _processEraseJob(db, core, inpainter, scratch, job);
    }
  } finally {
    core.scratchDestroy(scratch); // shared inpainter এখানে destroy করব না
    await db.close();
    control.close();
    cfg.toPool.send(WorkerStopped(cfg.workerId));
  }
}

Future<void> _processEraseJob(AppDatabase db, ScannerCore core,
    Pointer<ScInpainter> inpainter, Pointer<ScScratch> scratch, Job job) async {
  final page = await db.getPageById(job.targetId);
  if (page == null) { await db.markJobDone(job.id); return; }

  final p = job.checkpoint;
  final maskPath = p['maskPath'] as String?;
  if (maskPath == null) { await db.handleJobFailure(job, StateError('no mask')); return; }
  final srcPath = page.procPath ?? page.rawPath;
  final outPath = (p['outPath'] as String?) ?? srcPath;
  final tileSize = (p['tileSize'] as int?) ?? 512;
  final overlap = (p['overlap'] as int?) ?? 64;

  final srcView = calloc<ScImage>(), maskView = calloc<ScImage>(), outView = calloc<ScImage>();
  final cSrc = srcPath.toNativeUtf8(), cMask = maskPath.toNativeUtf8(), cOut = outPath.toNativeUtf8();
  final progress = ReceivePort();
  try {
    core.scratchReset(scratch);
    core.b.sc_scratch_load_file(scratch, cSrc.cast(), srcView);
    core.b.sc_scratch_load_file(scratch, cMask.cast(), maskView);
    await db.updateJobProgress(job.id, 0.10);

    core.inpaintRunScratchAsync(
        inpainter, scratch, srcView, maskView, tileSize, overlap, progress.sendPort.nativePort, outView);

    await for (final msg in progress) {
      final m = msg as List;
      final tag = m[0] as int;
      if (tag == kMsgProgress) {
        await db.updateJobProgress(job.id, 0.10 + 0.85 * ((m[1] as int) / 1000.0));
      } else if (tag == kMsgError) {
        throw ScException(m[1] as int, 'LaMa inpaint failed');
      } else if (tag == kMsgDone) {
        break;
      }
    }

    core.b.sc_scratch_save_file(scratch, outView, cOut.cast(), 92);
    await db.updateJobProgress(job.id, 0.98);

    await db.applyEraseResult(job.id, page.id, outPath, {
      'type': 'magic_erase', 'model': 'lama', 'mask': maskPath,
      'tileSize': tileSize, 'overlap': overlap,
      'at': DateTime.now().millisecondsSinceEpoch,
    });
  } catch (e) {
    await db.handleJobFailure(job, e);
  } finally {
    progress.close();
    core.scratchReset(scratch);
    for (final x in [srcView, maskView, outView]) calloc.free(x);
    for (final x in [cSrc, cMask, cOut]) calloc.free(x);
  }
}
