import 'package:flutter/widgets.dart';

/// Bengali-তে matra/reph উপরে-নিচে জায়গা দরকার → generous line height।
TextStyle bengaliStyle(double fontSizePx, {FontWeight weight = FontWeight.w400}) => TextStyle(
      fontFamily: 'NotoSansBengali',
      fontSize: fontSizePx,
      fontWeight: weight,
      height: 1.42,
      locale: const Locale('bn'),
      color: const Color(0xFF111111),
    );

class FitResult {
  const FitResult(this.fontSizePx, this.height);
  final double fontSizePx;
  final double height;
}

/// maxWidthPx-এ wrap; overflow হলে shrinkToFit করলে font ছোট করে, নাহলে grow।
FitResult fitText({
  required String text,
  required double maxWidthPx,
  required double baseFontPx,
  required double maxHeightPx,
  bool shrinkToFit = true,
  double minFontPx = 6,
}) {
  TextPainter paint(double fs) => TextPainter(
        text: TextSpan(text: text.isEmpty ? ' ' : text, style: bengaliStyle(fs)),
        textDirection: TextDirection.ltr,
        strutStyle: StrutStyle(fontSize: fs, height: 1.42, forceStrutHeight: true),
      )..layout(maxWidth: maxWidthPx);

  var painter = paint(baseFontPx);
  if (shrinkToFit && painter.height > maxHeightPx) {
    var lo = minFontPx, hi = baseFontPx;
    while (hi - lo > 0.5) {
      final mid = (lo + hi) / 2;
      painter = paint(mid);
      painter.height <= maxHeightPx ? lo = mid : hi = mid;
    }
    return FitResult(lo, paint(lo).height);
  }
  return FitResult(baseFontPx, painter.height);
}
