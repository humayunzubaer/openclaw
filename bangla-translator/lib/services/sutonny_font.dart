import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

/// Loads the SutonnyMJ font at runtime.
///
/// SutonnyMJ is a licensed font, so it is not shipped with the source. The
/// app uses `assets/fonts/SutonnyMJ.ttf` when it was bundled at build time,
/// otherwise a copy the user imported from the phone.
class SutonnyFont {
  static const family = 'SutonnyMJ';
  static const _assetPath = 'assets/fonts/SutonnyMJ.ttf';
  static const _importedName = 'SutonnyMJ.ttf';

  /// True once SutonnyMJ is registered with the engine.
  final loaded = ValueNotifier<bool>(false);

  Future<void> init() async {
    final bundled = await _loadAsset();
    if (bundled != null) {
      await _register(bundled);
      return;
    }
    final file = await _importedFile();
    if (await file.exists()) {
      await _register(await file.readAsBytes());
    }
  }

  /// Validates and stores a user-picked font file, then loads it.
  Future<void> import(Uint8List bytes) async {
    if (!isFontFile(bytes)) {
      throw const FormatException(
        'এটি কোনো ফন্ট ফাইল নয়। SutonnyMJ.ttf ফাইলটি বেছে নিন।',
      );
    }
    final file = await _importedFile();
    await file.writeAsBytes(bytes, flush: true);
    // A family can be registered only once per run; a replaced file is
    // picked up on the next launch.
    if (!loaded.value) await _register(bytes);
  }

  Future<Uint8List?> _loadAsset() async {
    try {
      final data = await rootBundle.load(_assetPath);
      return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    } catch (_) {
      // Not bundled in this build.
      return null;
    }
  }

  Future<File> _importedFile() async {
    final dir = await getApplicationSupportDirectory();
    return File('${dir.path}/$_importedName');
  }

  Future<void> _register(Uint8List bytes) async {
    final loader = FontLoader(family)
      ..addFont(Future.value(ByteData.sublistView(bytes)));
    await loader.load();
    loaded.value = true;
  }
}

/// TrueType/OpenType signature check.
bool isFontFile(Uint8List bytes) {
  if (bytes.length < 4) return false;
  final tag = (bytes[0] << 24) | (bytes[1] << 16) | (bytes[2] << 8) | bytes[3];
  const trueType = 0x00010000;
  const otto = 0x4F54544F; // 'OTTO'
  const trueMac = 0x74727565; // 'true'
  return tag == trueType || tag == otto || tag == trueMac;
}
