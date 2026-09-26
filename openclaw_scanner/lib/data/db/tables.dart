import 'package:drift/drift.dart';
import 'converters.dart';

@DataClassName('Folder')
class Folders extends Table {
  TextColumn get id => text()();
  TextColumn get name => text()();
  TextColumn get parentId => text().nullable().references(Folders, #id)();
  IntColumn get createdAt => integer()();
  @override
  Set<Column> get primaryKey => {id};
}

@DataClassName('Document')
@TableIndex(name: 'idx_doc_folder', columns: {#folderId})
class Documents extends Table {
  TextColumn get id => text()();
  TextColumn get folderId => text().nullable().references(Folders, #id)();
  TextColumn get title => text()();
  IntColumn get pageCount => integer().withDefault(const Constant(0))();
  TextColumn get ocrStatus =>
      textEnum<DocOcrStatus>().withDefault(Constant(DocOcrStatus.none.name))();
  TextColumn get lang => text().withDefault(const Constant('ben'))();
  IntColumn get createdAt => integer()();
  IntColumn get updatedAt => integer()();
  @override
  Set<Column> get primaryKey => {id};
}

@DataClassName('Page')
@TableIndex(name: 'idx_page_doc_seq', columns: {#documentId, #seq})
@TableIndex(name: 'idx_page_ocr', columns: {#ocrState})
class Pages extends Table {
  TextColumn get id => text()();
  TextColumn get documentId => text().references(Documents, #id)();
  IntColumn get seq => integer()();

  // File-system reference — pixel কখনো নয়।
  TextColumn get rawPath => text()(); // immutable original
  TextColumn get procPath => text().nullable()(); // regenerable, post-edit
  TextColumn get thumbPath => text().nullable()();

  IntColumn get width => integer()();
  IntColumn get height => integer()();
  TextColumn get captureMode =>
      textEnum<CaptureMode>().withDefault(Constant(CaptureMode.document.name))();

  // Non-destructive edit op-list (crop quad, filters, eraser strokes, textEdits)।
  TextColumn get editState =>
      text().map(const JsonMapConverter()).withDefault(const Constant('{}'))();

  TextColumn get ocrState =>
      textEnum<PageOcrState>().withDefault(Constant(PageOcrState.none.name))();
  @override
  Set<Column> get primaryKey => {id};
}

/// Word-level OCR box — in-scan edit reflow ও Word/Excel export-এর জন্য structured।
@DataClassName('OcrBlock')
@TableIndex(name: 'idx_block_page', columns: {#pageId})
class OcrBlocks extends Table {
  TextColumn get id => text()();
  TextColumn get pageId => text().references(Pages, #id)();
  TextColumn get text => text()();
  RealColumn get x => real()(); // normalized 0..1 bbox
  RealColumn get y => real()();
  RealColumn get w => real()();
  RealColumn get h => real()();
  RealColumn get confidence => real().withDefault(const Constant(0))();
  RealColumn get fontSize => real().nullable()();
  TextColumn get lineId => text().nullable()();
  TextColumn get source =>
      textEnum<TextSource>().withDefault(Constant(TextSource.typed.name))();
  @override
  Set<Column> get primaryKey => {id};
}

/// Persistent, restart-survivable work queue।
@DataClassName('Job')
@TableIndex(name: 'idx_job_claim', columns: {#state, #priority})
class Jobs extends Table {
  TextColumn get id => text()();
  TextColumn get type => textEnum<JobType>()();
  TextColumn get targetId => text()(); // pageId বা documentId
  IntColumn get priority => integer().withDefault(const Constant(100))();
  TextColumn get state =>
      textEnum<JobState>().withDefault(Constant(JobState.queued.name))();
  RealColumn get progress => real().withDefault(const Constant(0))();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
  TextColumn get checkpoint =>
      text().map(const JsonMapConverter()).withDefault(const Constant('{}'))();
  TextColumn get error => text().nullable()();
  IntColumn get createdAt => integer()();
  IntColumn get updatedAt => integer()();
  @override
  Set<Column> get primaryKey => {id};
}
