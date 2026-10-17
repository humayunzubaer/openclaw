import 'package:flutter/material.dart';

import '../bijoy/unicode_to_bijoy.dart';
import '../services/sutonny_font.dart';

/// Shows Unicode Bangla text drawn with SutonnyMJ (Bijoy encoding).
///
/// English words and signs SutonnyMJ cannot draw keep the normal font, the
/// way a typist switches fonts in a Bijoy document. Without the font the
/// Unicode text is shown with the system Bangla font.
class BijoyText extends StatelessWidget {
  const BijoyText(
    this.text, {
    super.key,
    required this.font,
    this.fontSize = 20,
  });

  final String text;
  final SutonnyFont font;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final base = Theme.of(context).textTheme.bodyLarge!
        .copyWith(fontSize: fontSize, height: 1.5);
    return ValueListenableBuilder<bool>(
      valueListenable: font.loaded,
      builder: (context, loaded, _) {
        if (!loaded) return SelectableText(text, style: base);
        final spans = [
          for (final segment in convertToSegments(text))
            TextSpan(
              text: segment.text,
              style: segment.isBijoy
                  ? base.copyWith(
                      fontFamily: SutonnyFont.family,
                      // SutonnyMJ glyphs are drawn smaller than Unicode
                      // Bangla fonts at the same size.
                      fontSize: fontSize * 1.15,
                    )
                  : base,
            ),
        ];
        return SelectableText.rich(TextSpan(children: spans));
      },
    );
  }
}
