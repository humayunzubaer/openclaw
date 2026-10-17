import 'dart:io';
import 'dart:ui' as ui;
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import '../editor/text/text_block_model.dart';
import 'export_source.dart';

/// প্রতি page-এ এক JPG। Baking dart:ui দিয়ে → conjunct ঠিকভাবে shape হয়।
class JpgExporter {
  JpgExporter(this.exportsDir);
  final Directory exportsDir;

  Future<List<String>> export(List<PageExport> pages, {int quality = 90}) async {
    final out = <String>[];
    for (final pe in pages) {
      final rgba = await _bake(pe); // root isolate (dart:ui)
      final w = pe.page.width, h = pe.page.height;
      final jpgBytes = await Future(() {
        final im = img.Image.fromBytes(
            width: w, height: h, bytes: rgba.buffer, order: img.ChannelOrder.rgba);
        return img.encodeJpg(im, quality: quality);
      });
      final path = p.join(exportsDir.path, '${pe.page.id}.jpg');
      await File(path).writeAsBytes(jpgBytes, flush: true);
      out.add(path);
    }
    return out;
  }

  Future<ui.ByteData> _bake(PageExport pe) async {
    final w = pe.page.width.toDouble(), h = pe.page.height.toDouble();
    final recorder = ui.PictureRecorder();
    final canvas = ui.Canvas(recorder, ui.Rect.fromLTWH(0, 0, w, h));

    final codec = await ui.instantiateImageCodec(
        await File(pe.page.procPath ?? pe.page.rawPath).readAsBytes());
    final frame = await codec.getNextFrame();
    canvas.drawImageRect(
        frame.image,
        ui.Rect.fromLTWH(0, 0, frame.image.width.toDouble(), frame.image.height.toDouble()),
        ui.Rect.fromLTWH(0, 0, w, h), ui.Paint());

    for (final b in pe.blocks) {
      final rect = ui.Rect.fromLTWH(
          b.rectN.left * w, b.rectN.top * h, b.rectN.width * w, b.rectN.height * h);
      canvas.drawRect(rect, ui.Paint()..color = const ui.Color(0xFFFFFFFF));
      final fontPx = b.fontSizeN * h;
      final pb = ui.ParagraphBuilder(ui.ParagraphStyle(
        textAlign: switch (b.align) {
          TextAlignH.center => ui.TextAlign.center,
          TextAlignH.right => ui.TextAlign.right,
          TextAlignH.left => ui.TextAlign.left,
        },
        fontFamily: 'NotoSansBengali',
        fontSize: fontPx,
        height: 1.42,
        locale: const ui.Locale('bn'),
      ))
        ..pushStyle(ui.TextStyle(color: const ui.Color(0xFF111111)))
        ..addText(b.text);
      final para = pb.build()..layout(ui.ParagraphConstraints(width: rect.width));
      canvas.drawParagraph(para, rect.topLeft);
    }

    final image = await recorder.endRecording().toImage(pe.page.width, pe.page.height);
    final data = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    image.dispose();
    frame.image.dispose();
    return data!;
  }
}
