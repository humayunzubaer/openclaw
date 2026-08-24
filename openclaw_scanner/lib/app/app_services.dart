import 'dart:async';
import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/isolate.dart';
import 'package:drift/native.dart';

import '../data/db/app_database.dart';
import '../editor/auto_analyzer.dart';
import '../editor/mask_compositor.dart';
import '../export/export_service.dart';
import '../export/jpg_exporter.dart';
import '../native/scanner_core.dart';
import '../pdf/pdf_manager.dart';
import '../pdf/pdf_service.dart';
import '../workers/magic_erase_pool.dart';
import '../workers/ocr_pool.dart';
import 'app_config.dart';
import 'app_paths.dart';
import 'background_guard.dart';

/// একমাত্র writer DriftIsolate-এ চলে। WAL দিলে UI read আর single writer একসাথে চলে।
DatabaseConnection _openConnection(String dbPath) {
  final exec = NativeDatabase(
    File(dbPath),
    setup: (raw) {
      raw.execute('PRAGMA journal_mode=WAL;');
      raw.execute('PRAGMA foreign_keys=ON;');
      raw.execute('PRAGMA busy_timeout=4000;');
    },
  );
  return DatabaseConnection(exec);
}

class AppServices {
  AppServices._(this.db, this.paths, this.ocr, this.eraser, this.autoAnalyzer,
      this.exportService, this.pdfManager, this._driftIsolate, this._bg);

  final AppDatabase db;
  final AppPaths paths;
  final OcrPool ocr;
  final MagicErasePool eraser;
  final AutoAnalyzer autoAnalyzer;
  final ExportService exportService;
  final PdfManager pdfManager;
  final DriftIsolate _driftIsolate;
  final BackgroundGuard _bg;
  StreamSubscription<bool>? _bgSub;

  static AppServices? _i;
  static AppServices get instance =>
      _i ?? (throw StateError('AppServices.boot() has not completed'));

  static Future<AppServices> boot({
    BackgroundGuard backgroundGuard = const NoopBackgroundGuard(),
    AppConfig config = const AppConfig(),
  }) async {
    if (_i != null) return _i!;

    final paths = await AppPaths.resolve();
    await paths.provisionAssets(config);

    // 1) THE single writer — beforeOpen() orphaned RUNNING job আবার queue করে।
    final driftIsolate = await DriftIsolate.spawn(() => _openConnection(paths.dbFile.path));
    final db = AppDatabase(await driftIsolate.connect());

    // 2) native API init (main isolate, একবার)
    ScannerCore.open().initDartApi();

    // 3) দুই pool একই writer-এ attach
    final ocr = await OcrPool.attach(
        mainDb: db, driftIsolate: driftIsolate, tessdataDir: paths.tessdataDir.path);
    final eraser = await MagicErasePool.boot(
        mainDb: db, driftIsolate: driftIsolate, lamaModelPath: paths.lamaModel.path);

    final autoAnalyzer = AutoAnalyzer.boot(handSegModelPath: paths.handSegModel.path);
    final exportService = ExportService(db, paths.exportsDir);
    final pdf = await PdfService.boot();
    final pdfManager = PdfManager(db, pdf, JpgExporter(paths.exportsDir), paths.exportsDir);

    final services = AppServices._(
        db, paths, ocr, eraser, autoAnalyzer, exportService, pdfManager, driftIsolate, backgroundGuard);
    services._bindBackground();
    return _i = services;
  }

  void _bindBackground() {
    _bgSub = db.watchHasPendingWork().distinct().listen((busy) {
      busy ? _bg.begin('Processing documents…') : _bg.end();
    });
  }

  // UI convenience
  Future<void> scanToOcr(String documentId) => ocr.enqueueDocument(documentId);
  Future<void> applyMagicErase(String pageId, {required String maskPath}) =>
      eraser.applyErase(pageId, maskPath: maskPath);
  Stream<double> watchOcrProgress(String documentId) => ocr.watchProgress(documentId);
  Stream<double> watchEraseProgress(String pageId) => eraser.watchProgress(pageId);
  MaskCompositor get maskCompositor => MaskCompositor(paths.masksDir);

  Future<void> dispose() async {
    await _bgSub?.cancel();
    await ocr.shutdown();
    await eraser.shutdown();
    await db.close();
    _driftIsolate.shutdownAll();
    _i = null;
  }
}
