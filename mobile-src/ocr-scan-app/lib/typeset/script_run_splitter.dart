import 'dart:ui';

/// লাইনের ভেতরে বাংলা আর ইংরেজি অংশ আলাদা করে — যাতে প্রতিটা অংশে আলাদা ফন্ট/সাইজ বসানো যায়।
/// digit/punctuation/space-কে "neutral" ধরা হয়েছে — এগুলো আশেপাশের script-এর সাথে মিশে
/// যায়, আলাদা করে নতুন run তৈরি করে না (নাহলে টেক্সট বেশি ভেঙে যেত)।
enum ScriptKind { bengali, latin }

class ScriptRun {
  ScriptRun(this.text, this.kind);
  final String text;
  final ScriptKind kind;
}

class ScriptRunSplitter {
  /// একটা লাইনকে বাংলা/ইংরেজি অংশে ভাগ করে, ক্রম ঠিক রেখে।
  static List<ScriptRun> split(String text) {
    if (text.isEmpty) return const [];

    final runs = <ScriptRun>[];
    final buf = StringBuffer();
    ScriptKind? current;

    void flush() {
      if (buf.isNotEmpty) {
        runs.add(ScriptRun(buf.toString(), current ?? ScriptKind.latin));
      }
      buf.clear();
    }

    for (final rune in text.runes) {
      final kind = _strongKindOf(rune); // null মানে neutral (digit/space/punctuation)
      if (kind != null && kind != current) {
        flush();
        current = kind;
      }
      buf.writeCharCode(rune);
    }
    flush();
    return runs;
  }

  /// বাংলা ইউনিকোড ব্লক (U+0980–U+09FF) বনাম ল্যাটিন অক্ষর — শক্তিশালী সংকেত।
  /// সংখ্যা/যতিচিহ্ন/স্পেসের জন্য null রিটার্ন করে (neutral, split করে না)।
  static ScriptKind? _strongKindOf(int rune) {
    if (rune >= 0x0980 && rune <= 0x09FF) return ScriptKind.bengali;
    final isAsciiLetter =
        (rune >= 0x0041 && rune <= 0x005A) || (rune >= 0x0061 && rune <= 0x007A);
    if (isAsciiLetter) return ScriptKind.latin;
    return null;
  }
}
