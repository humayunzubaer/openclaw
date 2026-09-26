import 'dart:io';
import 'package:camera/camera.dart';
import 'package:path/path.dart' as p;
import 'package:uuid/uuid.dart';
import '../app/app_services.dart';
import '../data/db/converters.dart';
import 'capture_processor.dart';

class ScanController {
  ScanController(this._services);
  final AppServices _services;
  late CameraController camera;
  String? _documentId;
  int _seq = 0;

  Future<void> init() async {
    final cams = await availableCameras();
    camera = CameraController(cams.first, ResolutionPreset.max, enableAudio: false);
    await camera.initialize();
  }

  Future<String> startDocument(String title) async {
    _documentId = await _services.db.createDocument(title);
    _seq = 0;
    return _documentId!;
  }

  /// High-speed multi-page: capture → mode-specific processing → Page persist।
  Future<void> capturePage(CaptureMode mode) async {
    final shot = await camera.takePicture();
    final dir = _services.paths.scansDir.path;
    final id = const Uuid().v4();
    final raw = p.join(dir, '${id}_raw.jpg');
    final proc = p.join(dir, '${id}_proc.jpg');
    final thumb = p.join(_services.paths.thumbsDir.path, '$id.jpg');
    await File(shot.path).copy(raw);

    final r = await processCapture(mode: mode, srcPath: raw, procPath: proc, thumbPath: thumb);
    await _services.db.addPage(
      pageId: id, documentId: _documentId!, seq: _seq++,
      rawPath: raw, procPath: r.procPath, thumbPath: r.thumbPath,
      width: r.width, height: r.height, mode: mode,
    );
  }

  Future<void> finishAndOcr() async => _services.scanToOcr(_documentId!);
  Future<void> dispose() => camera.dispose();
}
