import 'dart:io';
import 'package:flutter/services.dart' show rootBundle;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'app_config.dart';

class AppPaths {
  AppPaths(this.root);
  final Directory root;

  Directory get scansDir => Directory(p.join(root.path, 'scans'));
  Directory get thumbsDir => Directory(p.join(root.path, 'thumbs'));
  Directory get exportsDir => Directory(p.join(root.path, 'exports'));
  Directory get masksDir => Directory(p.join(root.path, 'masks'));
  Directory get tessdataDir => Directory(p.join(root.path, 'tessdata'));
  Directory get modelsDir => Directory(p.join(root.path, 'models'));
  File get dbFile => File(p.join(root.path, 'app.db'));
  File get lamaModel => File(p.join(modelsDir.path, 'lama_fp16.onnx'));
  File get handSegModel => File(p.join(modelsDir.path, 'handseg.onnx'));
  File get bengaliFont => File(p.join(modelsDir.path, 'NotoSansBengali-Regular.ttf'));

  static Future<AppPaths> resolve() async {
    final base = await getApplicationSupportDirectory();
    final paths = AppPaths(base);
    for (final d in [
      paths.scansDir, paths.thumbsDir, paths.exportsDir,
      paths.masksDir, paths.tessdataDir, paths.modelsDir,
    ]) {
      await d.create(recursive: true);
    }
    return paths;
  }

  /// Bundled model/font disk-এ copy (native code disk থেকে পড়ে)।
  Future<void> provisionAssets(AppConfig cfg) async {
    await _copyIfStale(cfg.tessdataAsset,
        File(p.join(tessdataDir.path, '${cfg.tessLang}.traineddata')), cfg.assetVersion);
    await _copyIfStale(cfg.lamaAsset, lamaModel, cfg.assetVersion);
    await _copyIfStale(cfg.handSegAsset, handSegModel, cfg.assetVersion);
    await _copyIfStale(cfg.bengaliFontAsset, bengaliFont, cfg.assetVersion);
  }

  Future<void> _copyIfStale(String assetKey, File dst, int version) async {
    final marker = File('${dst.path}.v');
    final fresh = await dst.exists() &&
        await marker.exists() &&
        (await marker.readAsString()) == '$version';
    if (fresh) return;
    final bytes = await rootBundle.load(assetKey);
    await dst.writeAsBytes(
        bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes), flush: true);
    await marker.writeAsString('$version', flush: true);
  }
}
