import 'package:google_mlkit_translation/google_mlkit_translation.dart';

/// Languages the app translates from. The target is always Bangla.
enum SourceLanguage {
  english(TranslateLanguage.english, 'ইংরেজি', 'English'),
  russian(TranslateLanguage.russian, 'রুশ', 'Русский');

  const SourceLanguage(this.mlKit, this.banglaName, this.nativeName);

  final TranslateLanguage mlKit;
  final String banglaName;
  final String nativeName;
}

/// Offline language pack as ML Kit stores it on the device.
enum LanguagePack {
  bangla(TranslateLanguage.bengali, 'বাংলা'),
  english(TranslateLanguage.english, 'ইংরেজি'),
  russian(TranslateLanguage.russian, 'রুশ');

  const LanguagePack(this.mlKit, this.banglaName);

  final TranslateLanguage mlKit;
  final String banglaName;

  String get code => mlKit.bcpCode;
}

/// On-device translation through Google ML Kit. Every pack is downloaded
/// once (about 30 MB each); after that translation needs no internet.
class TranslationService {
  final _models = OnDeviceTranslatorModelManager();
  final _translators = <SourceLanguage, OnDeviceTranslator>{};

  /// Packs needed for [source] -> Bangla. ML Kit pivots Russian through
  /// English, so Russian needs the English pack too.
  static List<LanguagePack> packsFor(SourceLanguage source) => switch (source) {
    SourceLanguage.english => const [LanguagePack.english, LanguagePack.bangla],
    SourceLanguage.russian => const [
      LanguagePack.russian,
      LanguagePack.english,
      LanguagePack.bangla,
    ],
  };

  Future<bool> isDownloaded(LanguagePack pack) =>
      _models.isModelDownloaded(pack.code);

  Future<bool> isReady(SourceLanguage source) async {
    for (final pack in packsFor(source)) {
      if (!await isDownloaded(pack)) return false;
    }
    return true;
  }

  Future<void> download(LanguagePack pack, {required bool wifiOnly}) async {
    final ok = await _models.downloadModel(pack.code, isWifiRequired: wifiOnly);
    if (!ok) {
      throw TranslationException(
        '${pack.banglaName} ভাষার প্যাক নামানো যায়নি।',
      );
    }
  }

  Future<void> delete(LanguagePack pack) async {
    await _closeTranslators();
    await _models.deleteModel(pack.code);
  }

  /// Translates [text] line by line so paragraphs and blank lines survive.
  Future<String> translate(String text, SourceLanguage source) async {
    if (!await isReady(source)) {
      throw TranslationException(
        '${source.banglaName} → বাংলা অনুবাদের জন্য ভাষার প্যাক এখনো নামানো হয়নি। '
        '"ভাষার প্যাক" পাতায় গিয়ে একবার ইন্টারনেট দিয়ে নামিয়ে নিন।',
      );
    }
    final translator = _translators.putIfAbsent(
      source,
      () => OnDeviceTranslator(
        sourceLanguage: source.mlKit,
        targetLanguage: TranslateLanguage.bengali,
      ),
    );
    final lines = text.split('\n');
    final out = <String>[];
    for (final line in lines) {
      if (line.trim().isEmpty) {
        out.add(line);
        continue;
      }
      final parts = <String>[];
      for (final chunk in splitForTranslation(line)) {
        parts.add((await translator.translateText(chunk)).trim());
      }
      out.add(parts.join(' '));
    }
    return out.join('\n');
  }

  Future<void> dispose() => _closeTranslators();

  Future<void> _closeTranslators() async {
    for (final t in _translators.values) {
      await t.close();
    }
    _translators.clear();
  }
}

/// Splits a long line at sentence ends so each request stays small.
List<String> splitForTranslation(String line, {int maxLength = 400}) {
  final trimmed = line.trim();
  if (trimmed.length <= maxLength) return [trimmed];
  final sentences = RegExp(r'[^.!?…]+[.!?…]*\s*')
      .allMatches(trimmed)
      .map((m) => m.group(0)!)
      .toList();
  final chunks = <String>[];
  final current = StringBuffer();
  for (final sentence in sentences) {
    if (current.isNotEmpty && current.length + sentence.length > maxLength) {
      chunks.add(current.toString().trim());
      current.clear();
    }
    current.write(sentence);
  }
  if (current.isNotEmpty) chunks.add(current.toString().trim());
  return chunks;
}

class TranslationException implements Exception {
  TranslationException(this.message);

  final String message;

  @override
  String toString() => message;
}
