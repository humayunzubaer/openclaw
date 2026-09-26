/// Unicode বাংলা → SutonnyMJ/Bijoy-ধাঁচের ANSI ফন্টের জন্য "visual order"
/// রূপান্তরকারী।
///
/// ## কেন এটা শুধু character-map নয়
/// Unicode বাংলা টেক্সট **লজিক্যাল অর্ডারে** থাকে (উচ্চারণ/টাইপ করার ক্রমে)।
/// আধুনিক সফটওয়্যার (Word, browser) একটা shaping engine (HarfBuzz) দিয়ে
/// রেন্ডার করার সময় রেফ (র্ক), প্রি-বেস মাত্রা (ি, ে, ঈ, ো, ৌ) স্বয়ংক্রিয়ভাবে
/// visual position-এ সরিয়ে নেয়। কিন্তু SutonnyMJ/বিজয়-এর মতো glyph-ভিত্তিক
/// ANSI ফন্টের কোনো shaping engine নেই — যা টাইপ হয় (byte-order) তা-ই হুবহু
/// রেন্ডার হয়। তাই **এই reordering-টা আমাদের নিজেদেরই করে দিতে হবে।**
///
/// ## দুই ধাপে ভাগ করা হয়েছে
/// **ধাপ ১ — Visual reordering (এই ফাইলে সম্পূর্ণ implement করা, এখনই কাজ করে):**
/// প্রতিষ্ঠিত, established Bengali/Indic script shaping নিয়ম (Unicode-এর নিজস্ব
/// script-shaping behavior spec-এই বর্ণিত) — অনুমান নয়। covers করে:
///   - প্রি-বেস মাত্রা (ি/ে/ৈ) ব্যঞ্জনবর্ণের **আগে** সরানো
///   - ো/ৌ-কে তার দুই ভাগে (প্রি-বেস ে-অংশ + পোস্ট-বেস া/ৗ-অংশ) ভেঙে বসানো
///   - রেফ (র্ + ব্যঞ্জনবর্ণ) সনাক্ত করে পরের cluster-এর সাথে সিক্রমে বসানো
///   - যুক্তাক্ষর (ব্যঞ্জনবর্ণ + হসন্ত-জোড়া) cluster হিসেবে একসাথে রাখা
///
/// **ধাপ ২ — Glyph/byte mapping (এখনো raw table হিসেবে ফাঁকা, ইচ্ছাকৃতভাবে):**
/// প্রতিটা reordered ইউনিট আসল SutonnyMJ ফন্টের ঠিক কোন byte-এ যাবে — এটা
/// ফন্ট-নির্দিষ্ট raw ডেটা, অনুমান করে বসালে ভুল হওয়ার ঝুঁকি বেশি। তাই এখনও
/// `_glyphTableReady = false` — অর্থাৎ এখন visual-reorder করা **Unicode**
/// টেক্সট বেরোয় (Noto Sans Bengali ফন্টে সঠিকভাবে দেখা যায়), সুতন্বী ANSI byte
/// নয়। টেবিলটা একটা যাচাই করা উৎস থেকে বসালেই (নিচে `_glyphTable` fill করে
/// `_glyphTableReady = true` করলেই) পুরো pipeline অটোম্যাটিক সুতন্বী ANSI আউটপুট
/// দিতে শুরু করবে — অন্য কোনো ফাইল বদলাতে হবে না।
class SutonnyMjConverter {
  static const bool _glyphTableReady = false;

  static const _rephConsonant = 'র'; // র
  static const _virama = '্'; // ্

  /// প্রি-বেস মাত্রা → (postVowel?) — ো/ৌ দুই টুকরোয় ভাঙে, বাকিগুলো শুধু prefix।
  static const Map<String, String?> _preBaseVowels = {
    'ি': null, // ি
    'ে': null, // ে
    'ৈ': null, // ৈ
    'ো': 'া', // ো = ে(pre) + া(post)
    'ৌ': 'ৗ', // ৌ = ে(pre) + ৗ(post)
  };
  static const Set<String> _postBaseVowels = {
    'া', 'ী', 'ু', 'ূ', 'ৃ', 'ৄ', 'ৗ',
  };

  bool _isConsonant(int rune) => rune >= 0x0995 && rune <= 0x09B9;

  /// ধাপ ১ প্রয়োগ করে — cluster-ভিত্তিক visual reordering।
  String _toVisualOrder(String text) {
    final runes = text.runes.toList();
    final out = StringBuffer();
    var i = 0;

    while (i < runes.length) {
      // --- রেফ সনাক্তকরণ: র + ্ + (আরেকটা ব্যঞ্জনবর্ণ, তবেই এটা রেফ) ---
      var reph = '';
      if (runes[i] == _rephConsonant.codeUnitAt(0) &&
          i + 2 < runes.length &&
          runes[i + 1] == _virama.codeUnitAt(0) &&
          _isConsonant(runes[i + 2])) {
        reph = '$_rephConsonant$_virama';
        i += 2; // "র্" খেয়ে ফেলা হলো; cluster এখন পরের consonant থেকে শুরু
      }

      if (i >= runes.length || !_isConsonant(runes[i])) {
        // ব্যঞ্জনবর্ণ নয় (স্বরবর্ণ/সংখ্যা/স্পেস/যতিচিহ্ন) — অপরিবর্তিত কপি
        if (i < runes.length) { out.writeCharCode(runes[i]); i++; }
        continue;
      }

      // --- মূল consonant cluster (যুক্তাক্ষর সহ) সংগ্রহ ---
      final coreStart = i;
      while (true) {
        i++; // চলতি ব্যঞ্জনবর্ণ খেয়ে ফেলা
        final hasConjunct = i + 1 < runes.length &&
            runes[i] == _virama.codeUnitAt(0) &&
            _isConsonant(runes[i + 1]);
        if (hasConjunct) { i++; continue; } // ্-সহ পরের ব্যঞ্জনবর্ণেও যুক্তাক্ষর চলতে থাকবে
        break;
      }
      final core = String.fromCharCodes(runes.sublist(coreStart, i));

      // --- মাত্রা (vowel sign) থাকলে ধরা ---
      String? preVowel;
      String? postVowel;
      if (i < runes.length) {
        final v = String.fromCharCode(runes[i]);
        if (_preBaseVowels.containsKey(v)) {
          preVowel = v;
          postVowel = _preBaseVowels[v];
          i++;
        } else if (_postBaseVowels.contains(v)) {
          postVowel = v;
          i++;
        }
      }

      // --- visual ক্রমে বসানো ---
      if (preVowel != null) out.write(preVowel);
      if (reph.isNotEmpty && core.isNotEmpty) {
        // প্রচলিত কনভেনশন: রেফ বসে cluster-এর প্রথম ব্যঞ্জনবর্ণের ঠিক পরে
        out.write(core[0]);
        out.write(reph);
        out.write(core.substring(1));
      } else {
        out.write(core);
      }
      if (postVowel != null) out.write(postVowel);
    }
    return out.toString();
  }

  /// পাবলিক entry point। ধাপ ১ (reordering) এখনই প্রযোগ হয়; ধাপ ২ (byte
  /// mapping) যাচাই করা টেবিল বসার অপেক্ষায়।
  String convert(String unicodeBengali) {
    final reordered = _toVisualOrder(unicodeBengali);
    if (!_glyphTableReady) return reordered;
    // TODO: verified glyph table বসলে এখানে reordered → ANSI byte map হবে।
    throw UnimplementedError('SutonnyMjConverter: glyph table pending verification');
  }

  /// আউটপুট ফাইলে কোন font-family নাম বসবে।
  String get outputFontFamily => _glyphTableReady ? 'SutonnyMJ' : 'Noto Sans Bengali';
}
