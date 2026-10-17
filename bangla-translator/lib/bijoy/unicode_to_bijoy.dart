import 'bijoy_tables.dart';

/// A run of output text. Bijoy runs must be drawn with the SutonnyMJ font;
/// plain runs (English words, punctuation, unsupported signs) must not,
/// because SutonnyMJ maps Latin code points to Bangla glyphs.
class BijoySegment {
  const BijoySegment(this.text, {required this.isBijoy});

  final String text;
  final bool isBijoy;

  @override
  bool operator ==(Object other) =>
      other is BijoySegment && other.text == text && other.isBijoy == isBijoy;

  @override
  int get hashCode => Object.hash(text, isBijoy);

  @override
  String toString() => '${isBijoy ? 'B' : 'U'}:$text';
}

const _halant = '্';
const _zwnj = '‌';
const _zwj = '‍';

const _preKars = {'ি', 'ে', 'ৈ'};
const _belowKars = {'ু', 'ূ', 'ৃ'};
const _spacingKars = {'া', 'ী', 'ৗ'};
const _modifiers = {'ং', 'ঃ'};
const _chandrabindu = 'ঁ';

const _independentVowels = {
  'অ', 'আ', 'ই', 'ঈ', 'উ', 'ঊ', 'ঋ', 'এ', 'ঐ', 'ও', 'ঔ', //
};

bool _isConsonant(String c) {
  if (c.isEmpty) return false;
  final u = c.codeUnitAt(0);
  // ক..হ, ড় ঢ় য়, ৎ
  return (u >= 0x0995 && u <= 0x09B9 && bijoyGlyphs.containsKey(c)) ||
      u == 0x09DC ||
      u == 0x09DD ||
      u == 0x09DF ||
      u == 0x09CE;
}

bool _isBanglaWordChar(int u) =>
    (u >= 0x0980 && u <= 0x09FF) || u == 0x200C || u == 0x200D;

bool _isAsciiDigit(int u) => u >= 0x30 && u <= 0x39;

final int _maxKeyLength = bijoyGlyphs.keys.fold(
  0,
  (m, k) => k.length > m ? k.length : m,
);

/// Brings decomposed and composed spellings to one canonical form.
String normalizeBangla(String text) {
  return text
      .replaceAll('\u09A1\u09BC', '\u09DC') // ড়
      .replaceAll('\u09A2\u09BC', '\u09DD') // ঢ়
      .replaceAll('\u09AF\u09BC', '\u09DF') // য়
      .replaceAll('\u09CB', '\u09C7\u09BE') // ো -> ে + া
      .replaceAll('\u09CC', '\u09C7\u09D7') // ৌ -> ে + ৗ
      .replaceAll('\u0985\u09BE', '\u0986'); // অ + া -> আ
}

/// Converts Unicode Bangla text to Bijoy (SutonnyMJ ANSI) text.
///
/// Non-Bangla text is kept as-is, so the result is exactly what a Bijoy
/// typist would paste into a SutonnyMJ document.
String unicodeToBijoy(String text) =>
    convertToSegments(text).map((s) => s.text).join();

/// Converts Unicode text into font runs: Bangla words become Bijoy runs,
/// everything else stays Unicode.
List<BijoySegment> convertToSegments(String input) {
  final text = normalizeBangla(input);
  final out = _SegmentBuilder();
  var i = 0;
  while (i < text.length) {
    final u = text.codeUnitAt(i);
    if (_isBanglaWordChar(u)) {
      var j = i;
      while (j < text.length && _isBanglaWordChar(text.codeUnitAt(j))) {
        j++;
      }
      final word = text.substring(i, j);
      final converted = _convertWord(word);
      if (converted == null) {
        out.add(word, isBijoy: false);
      } else {
        out.add(converted, isBijoy: true);
      }
      i = j;
      continue;
    }
    final ch = text[i];
    final punctuation = bijoyPunctuation[ch];
    if (punctuation != null) {
      out.add(punctuation, isBijoy: true);
    } else if (_isAsciiDigit(u)) {
      // SutonnyMJ draws 0-9 as Bangla digits, as a Bijoy typist would type.
      out.add(ch, isBijoy: true);
    } else {
      out.add(ch, isBijoy: false);
    }
    i++;
  }
  return out.build();
}

/// Converts one Bangla word, or returns null when it holds a sign that
/// SutonnyMJ cannot draw (the word is then shown in Unicode).
String? _convertWord(String word) {
  final chars = word.split('');
  final buffer = StringBuffer();
  var i = 0;
  var wordStart = true;
  while (i < chars.length) {
    final syllable = _readSyllable(chars, i);
    if (syllable == null) return null;
    buffer.write(_renderSyllable(syllable, wordStart: wordStart));
    wordStart = false;
    i = syllable.end;
  }
  return buffer.toString();
}

class _Syllable {
  _Syllable({required this.end});

  int end;
  bool reph = false;
  String body = '';
  String preKar = '';
  String belowKars = '';
  String spacingKars = '';
  String chandrabindu = '';
  String modifiers = '';
}

String _at(List<String> chars, int i) =>
    i >= 0 && i < chars.length ? chars[i] : '';

_Syllable? _readSyllable(List<String> c, int start) {
  final s = _Syllable(end: start);
  var i = start;
  final first = _at(c, i);

  if (_independentVowels.contains(first)) {
    if (first == 'আ') {
      s.body = 'অ';
      s.spacingKars = 'া';
    } else {
      s.body = first;
    }
    i++;
  } else if (_isConsonant(first)) {
    // র্ + consonant at the start of a syllable is a reph (রেফ).
    if (first == 'র' &&
        _at(c, i + 1) == _halant &&
        _isConsonant(_at(c, i + 2))) {
      s.reph = true;
      i += 2;
    }
    final body = StringBuffer(_at(c, i));
    i++;
    while (true) {
      final next = _at(c, i);
      if (next == _halant && _isConsonant(_at(c, i + 1))) {
        body.write(next);
        body.write(_at(c, i + 1));
        i += 2;
      } else if ((next == _zwj || next == _zwnj) &&
          _at(c, i + 1) == _halant &&
          _isConsonant(_at(c, i + 2))) {
        body.write(next);
        body.write(_halant);
        body.write(_at(c, i + 2));
        i += 3;
      } else if (next == _halant) {
        // Explicit hasanta (e.g. word-final ক্).
        body.write(next);
        i++;
        break;
      } else {
        break;
      }
    }
    s.body = body.toString();
  } else if (bijoyGlyphs.containsKey(first) && !_isSign(first)) {
    // Digit.
    s.body = first;
    s.end = i + 1;
    return s;
  } else if (first == _zwj || first == _zwnj) {
    s.end = i + 1;
    return s;
  } else if (!_isSign(first)) {
    return null;
  }

  // Vowel signs and modifiers. A sign without a base is drawn on its own.
  while (i < c.length) {
    final ch = c[i];
    if (_preKars.contains(ch)) {
      if (s.preKar.isNotEmpty) break;
      s.preKar = ch;
    } else if (_belowKars.contains(ch)) {
      s.belowKars += ch;
    } else if (_spacingKars.contains(ch)) {
      s.spacingKars += ch;
    } else if (ch == _chandrabindu) {
      s.chandrabindu += ch;
    } else if (_modifiers.contains(ch)) {
      s.modifiers += ch;
    } else {
      break;
    }
    i++;
  }
  s.end = i;
  return s;
}

bool _isSign(String c) =>
    _preKars.contains(c) ||
    _belowKars.contains(c) ||
    _spacingKars.contains(c) ||
    c == _chandrabindu ||
    _modifiers.contains(c);

String _renderSyllable(_Syllable s, {required bool wordStart}) {
  final out = StringBuffer();
  if (s.preKar.isNotEmpty) {
    // Bijoy uses the wider ‡/‰ shapes inside a word and †/ˆ at its start.
    final glyph = bijoyGlyphs[s.preKar]!;
    if (wordStart && glyph == '‡') {
      out.write('†');
    } else if (wordStart && glyph == '‰') {
      out.write('ˆ');
    } else {
      out.write(glyph);
    }
  }
  out.write(_applyVariants(_mapGreedy(s.body + s.belowKars)));
  if (s.reph) out.write('©');
  if (s.chandrabindu.isNotEmpty) out.write(_mapGreedy(s.chandrabindu));
  out.write(_mapGreedy(s.spacingKars));
  out.write(_mapGreedy(s.modifiers));
  return out.toString();
}

String _mapGreedy(String text) {
  final out = StringBuffer();
  var i = 0;
  while (i < text.length) {
    var matched = false;
    final maxLen = (text.length - i) < _maxKeyLength
        ? text.length - i
        : _maxKeyLength;
    for (var len = maxLen; len > 0; len--) {
      final glyph = bijoyGlyphs[text.substring(i, i + len)];
      if (glyph != null) {
        out.write(glyph);
        i += len;
        matched = true;
        break;
      }
    }
    if (!matched) {
      // ZWJ/ZWNJ that did not form a known conjunct carry no glyph.
      i++;
    }
  }
  return out.toString();
}

String _applyVariants(String body) {
  var result = body;
  for (final (from, to) in bijoyVariantFixups) {
    result = result.replaceAll(from, to);
  }
  // In Bijoy, y/~/… only ever stand for ু/ূ/ৃ, so swap in the alternate
  // shape after any letter that needs it.
  for (final base in bijoyAltUKarBases) {
    result = result
        .replaceAll('${base}y', '${base}z')
        .replaceAll('$base~', '$base‚');
  }
  for (final base in bijoyAltRiKarBases) {
    result = result.replaceAll('$base…', '$base„');
  }
  return result;
}

class _SegmentBuilder {
  final _segments = <BijoySegment>[];
  final _current = StringBuffer();
  bool? _currentIsBijoy;

  void add(String text, {required bool isBijoy}) {
    if (_currentIsBijoy != null && _currentIsBijoy != isBijoy) _flush();
    _currentIsBijoy = isBijoy;
    _current.write(text);
  }

  void _flush() {
    if (_current.isEmpty) return;
    _segments.add(BijoySegment(_current.toString(), isBijoy: _currentIsBijoy!));
    _current.clear();
  }

  List<BijoySegment> build() {
    _flush();
    return _segments;
  }
}
