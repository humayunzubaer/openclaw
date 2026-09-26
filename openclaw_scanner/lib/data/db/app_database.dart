import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';
import 'tables.dart';
import 'converters.dart';
import 'queue_stats.dart';

part 'app_database.g.dart'; // dart run build_runner build

@DriftDatabase(
  tables: [Folders, Documents, Pages, OcrBlocks, Jobs],
  include: {'search.drift'},
)
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.e);

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) async => m.createAll(), // tables + FTS5 virtual table
        beforeOpen: (details) async {
          await customStatement('PRAGMA foreign_keys = ON');
          // Hard kill থেকে recovery: RUNNING job আবার QUEUED।
          await (update(jobs)..where((j) => j.state.equalsValue(JobState.running)))
              .write(const JobsCompanion(state: Value(JobState.queued)));
        },
      );

  int get _now => DateTime.now().millisecondsSinceEpoch;

  // ------------------------------------------------------------------ documents/pages
  Future<String> createDocument(String title) async {
    final id = const Uuid().v4();
    await into(documents).insert(DocumentsCompanion.insert(
        id: id, title: title, createdAt: _now, updatedAt: _now));
    return id;
  }

  Future<void> addPage({
    required String pageId,
    required String documentId,
    required int seq,
    required String rawPath,
    required String procPath,
    required String thumbPath,
    required int width,
    required int height,
    required CaptureMode mode,
  }) =>
      transaction(() async {
        await into(pages).insert(PagesCompanion.insert(
          id: pageId, documentId: documentId, seq: seq,
          rawPath: rawPath, procPath: Value(procPath), thumbPath: Value(thumbPath),
          width: width, height: height, captureMode: Value(mode),
        ));
        await customStatement(
          'UPDATE documents SET page_count = page_count + 1, updated_at = ? WHERE id = ?',
          [_now, documentId]);
      });

  Stream<List<Document>> watchDocuments() =>
      (select(documents)..orderBy([(d) => OrderingTerm.desc(d.updatedAt)])).watch();

  Future<List<Page>> pagesOfOrdered(String documentId) =>
      (select(pages)
            ..where((p) => p.documentId.equals(documentId))
            ..orderBy([(p) => OrderingTerm.asc(p.seq)]))
          .get();

  Future<Page?> getPageById(String id) =>
      (select(pages)..where((p) => p.id.equals(id))).getSingleOrNull();

  Future<List<OcrBlock>> getOcrBlocks(String pageId) =>
      (select(ocrBlocks)
            ..where((b) => b.pageId.equals(pageId))
            ..orderBy([(b) => OrderingTerm.asc(b.y), (b) => OrderingTerm.asc(b.x)]))
          .get();

  // ------------------------------------------------------------------ OCR queue
  Future<void> enqueueDocumentOcr(String documentId) => transaction(() async {
        final docPages = await pagesOfOrdered(documentId);
        for (final p in docPages) {
          await into(jobs).insert(JobsCompanion.insert(
            id: 'job_${p.id}', type: JobType.ocr, targetId: p.id,
            priority: Value(p.seq), createdAt: _now, updatedAt: _now,
          ));
          await (update(pages)..where((t) => t.id.equals(p.id)))
              .write(const PagesCompanion(ocrState: Value(PageOcrState.queued)));
        }
      });

  /// Atomically claim next job — transaction writer serialize করায় race-free।
  Future<Job?> claimNextJob(Set<JobType> types) => transaction(() async {
        final next = await (select(jobs)
              ..where((j) =>
                  j.state.equalsValue(JobState.queued) & j.type.isInValues(types))
              ..orderBy([(j) => OrderingTerm.asc(j.priority)])
              ..limit(1))
            .getSingleOrNull();
        if (next == null) return null;
        await (update(jobs)..where((j) => j.id.equals(next.id)))
            .write(JobsCompanion(state: const Value(JobState.running), updatedAt: Value(_now)));
        return next.copyWith(state: JobState.running);
      });

  Future<void> updateJobProgress(String jobId, double p) =>
      (update(jobs)..where((j) => j.id.equals(jobId)))
          .write(JobsCompanion(progress: Value(p), updatedAt: Value(_now)));

  Future<void> markJobDone(String jobId) =>
      (update(jobs)..where((j) => j.id.equals(jobId))).write(JobsCompanion(
        state: const Value(JobState.done), progress: const Value(1), updatedAt: Value(_now)));

  /// OCR failure: 3 attempt পর্যন্ত backoff retry, তারপর job+page fail।
  Future<void> handleOcrFailure(Job job, String pageId, Object err) {
    final giveUp = job.attempts + 1 >= 3;
    return transaction(() async {
      await (update(jobs)..where((j) => j.id.equals(job.id))).write(JobsCompanion(
        state: Value(giveUp ? JobState.failed : JobState.queued),
        attempts: Value(job.attempts + 1),
        error: Value(err.toString()),
        updatedAt: Value(_now),
      ));
      if (giveUp) {
        await (update(pages)..where((p) => p.id.equals(pageId)))
            .write(const PagesCompanion(ocrState: Value(PageOcrState.failed)));
      }
    });
  }

  /// Non-OCR job-এর জন্য generic retry/backoff।
  Future<void> handleJobFailure(Job job, Object err) {
    final giveUp = job.attempts + 1 >= 3;
    return (update(jobs)..where((j) => j.id.equals(job.id))).write(JobsCompanion(
      state: Value(giveUp ? JobState.failed : JobState.queued),
      attempts: Value(job.attempts + 1),
      error: Value(err.toString()),
      updatedAt: Value(_now),
    ));
  }

  Future<void> cancelDocumentOcr(String documentId) => transaction(() async {
        final ids = await (select(pages)..where((p) => p.documentId.equals(documentId)))
            .map((p) => p.id)
            .get();
        await (update(jobs)
              ..where((j) =>
                  j.targetId.isIn(ids) & j.state.equalsValue(JobState.queued)))
            .write(JobsCompanion(state: const Value(JobState.cancelled), updatedAt: Value(_now)));
      });

  /// এক page-এর OCR result: word block + FTS text + status, এক transaction-এ।
  Future<void> writeOcrResult(
      String jobId, String pageId, List<OcrBlocksCompanion> blocks) {
    return transaction(() async {
      await (delete(ocrBlocks)..where((b) => b.pageId.equals(pageId))).go();
      await batch((b) => b.insertAll(ocrBlocks, blocks));

      final pageText = blocks.map((b) => b.text.value).join(' ');
      await customStatement('DELETE FROM page_fts WHERE page_id = ?', [pageId]);
      await customStatement(
          'INSERT INTO page_fts(page_id, content) VALUES (?, ?)', [pageId, pageText]);

      await (update(pages)..where((p) => p.id.equals(pageId)))
          .write(const PagesCompanion(ocrState: Value(PageOcrState.done)));
      await (update(jobs)..where((j) => j.id.equals(jobId))).write(JobsCompanion(
          state: const Value(JobState.done), progress: const Value(1), updatedAt: Value(_now)));
    });
  }

  Future<void> refreshDocOcrStatus(String documentId) => transaction(() async {
        final row = await customSelect(
          'SELECT SUM(ocr_state = ?2) AS done, '
          'SUM(ocr_state IN (?3, ?4)) AS terminal_other, COUNT(*) AS total '
          'FROM pages WHERE document_id = ?1',
          variables: [
            Variable(documentId),
            Variable(PageOcrState.done.name),
            Variable(PageOcrState.failed.name),
            Variable(PageOcrState.skipped.name),
          ],
          readsFrom: {pages},
        ).getSingle();

        final done = row.read<int>('done');
        final total = row.read<int>('total');
        final terminalOther = row.read<int>('terminal_other');
        final status = done == total
            ? DocOcrStatus.complete
            : (done + terminalOther == total && done > 0)
                ? DocOcrStatus.partial
                : DocOcrStatus.none;
        if (status != DocOcrStatus.none) {
          await (update(documents)..where((d) => d.id.equals(documentId)))
              .write(DocumentsCompanion(ocrStatus: Value(status), updatedAt: Value(_now)));
        }
      });

  Stream<double> watchDocumentOcrProgress(String documentId) {
    final q = customSelect(
      'SELECT COALESCE(AVG(j.progress),0) AS p FROM jobs j '
      'JOIN pages pg ON pg.id = j.target_id '
      'WHERE pg.document_id = ?1 AND j.type = ?2',
      variables: [Variable(documentId), Variable(JobType.ocr.name)],
      readsFrom: {jobs, pages},
    );
    return q.watchSingle().map((r) => r.read<double>('p'));
  }

  // ------------------------------------------------------------------ Magic Eraser
  Future<void> enqueueMagicErase(
    String pageId, {
    required String maskPath,
    int tileSize = 512,
    int overlap = 64,
    String? outPath,
  }) =>
      into(jobs).insert(JobsCompanion.insert(
        id: 'erase_${pageId}_$_now',
        type: JobType.magicErase,
        targetId: pageId,
        priority: const Value(10), // interactive edit
        checkpoint: Value({
          'maskPath': maskPath,
          'tileSize': tileSize,
          'overlap': overlap,
          if (outPath != null) 'outPath': outPath,
        }),
        createdAt: _now, updatedAt: _now,
      ));

  /// Cleaned image-এ proc point করে + replayable non-destructive op যোগ করে।
  Future<void> applyEraseResult(
      String jobId, String pageId, String newProcPath, Map<String, dynamic> op) =>
      transaction(() async {
        final page = await getPageById(pageId);
        final state = Map<String, dynamic>.from(page?.editState ?? const {});
        final ops = List<Map<String, dynamic>>.from(state['ops'] as List? ?? const []);
        ops.add(op);
        state['ops'] = ops;
        await (update(pages)..where((p) => p.id.equals(pageId)))
            .write(PagesCompanion(procPath: Value(newProcPath), editState: Value(state)));
        await markJobDone(jobId);
      });

  Stream<double> watchEraseProgress(String pageId) {
    final q = customSelect(
      'SELECT COALESCE(MAX(progress),0) AS p FROM jobs '
      'WHERE target_id = ?1 AND type = ?2 AND state IN (?3, ?4)',
      variables: [
        Variable(pageId),
        Variable(JobType.magicErase.name),
        Variable(JobState.queued.name),
        Variable(JobState.running.name),
      ],
      readsFrom: {jobs},
    );
    return q.watchSingle().map((r) => r.read<double>('p'));
  }

  // ------------------------------------------------------------------ text edits
  Future<void> saveTextEdits(String pageId, List<Map<String, dynamic>> blockJson) =>
      transaction(() async {
        final page = await getPageById(pageId);
        final state = Map<String, dynamic>.from(page?.editState ?? const {});
        state['textEdits'] = blockJson;
        await (update(pages)..where((p) => p.id.equals(pageId)))
            .write(PagesCompanion(editState: Value(state)));
        final edited = blockJson.map((e) => e['text'] as String).join(' ');
        await customStatement('DELETE FROM page_fts WHERE page_id = ?', [pageId]);
        await customStatement(
            'INSERT INTO page_fts(page_id, content) VALUES (?, ?)', [pageId, edited]);
      });

  // ------------------------------------------------------------------ ops surface
  Stream<bool> watchHasPendingWork() {
    final q = customSelect(
      'SELECT EXISTS(SELECT 1 FROM jobs WHERE state IN (?1, ?2)) AS busy',
      variables: [Variable(JobState.queued.name), Variable(JobState.running.name)],
      readsFrom: {jobs},
    );
    return q.watchSingle().map((r) => r.read<int>('busy') == 1);
  }

  Stream<QueueStats> watchQueueStats() {
    final q = customSelect(
      'SELECT type, state, COUNT(*) AS n FROM jobs GROUP BY type, state',
      readsFrom: {jobs},
    );
    return q.watch().map(QueueStats.fromRows);
  }
}
