import 'dart:isolate';
import '../native/scanner_core.dart';
import '../native/scanner_core_bindings.g.dart';
import 'package:ffi/ffi.dart';
import 'dart:ffi';

sealed class _PdfCmd {}
class _CountCmd extends _PdfCmd { _CountCmd(this.path); final String path; }
class _ExtractCmd extends _PdfCmd { _ExtractCmd(this.src, this.idx, this.out); final String src; final List<int> idx; final String out; }
class _CombineCmd extends _PdfCmd { _CombineCmd(this.srcs, this.out); final List<String> srcs; final String out; }
class _CompressCmd extends _PdfCmd { _CompressCmd(this.src, this.dpi, this.q, this.out); final String src; final int dpi, q; final String out; }
class _FromImagesCmd extends _PdfCmd { _FromImagesCmd(this.jpgs, this.wPt, this.hPt, this.out); final List<String> jpgs; final double wPt, hPt; final String out; }
class _AddLayerCmd extends _PdfCmd { _AddLayerCmd(this.pdfIn, this.pdfOut, this.fontPath, this.json); final String pdfIn, pdfOut, fontPath, json; }

class _Req { _Req(this.cmd, this.reply); final _PdfCmd cmd; final SendPort reply; }

/// PDFium thread-safe নয় → এক long-lived isolate, একবার init, calls serialize।
class PdfService {
  PdfService._(this._commands);
  final SendPort _commands;

  static Future<PdfService> boot() async {
    final ready = ReceivePort();
    await Isolate.spawn(_isolateMain, ready.sendPort);
    return PdfService._(await ready.first as SendPort);
  }

  Future<Object?> _call(_PdfCmd cmd) async {
    final reply = ReceivePort();
    _commands.send(_Req(cmd, reply.sendPort));
    final r = await reply.first;
    reply.close();
    if (r is String && r.startsWith('__err__:')) throw StateError(r.substring(8));
    return r;
  }

  Future<int> pageCount(String path) async => await _call(_CountCmd(path)) as int;
  Future<String> extract(String src, List<int> pages, String out) =>
      _call(_ExtractCmd(src, pages, out)).then((_) => out);
  Future<String> combine(List<String> srcs, String out) =>
      _call(_CombineCmd(srcs, out)).then((_) => out);
  Future<String> compress(String src, String out, {int dpi = 200, int quality = 75}) =>
      _call(_CompressCmd(src, dpi, quality, out)).then((_) => out);
  Future<String> fromImages(List<String> jpgs, String out, {double wPt = 595, double hPt = 842}) =>
      _call(_FromImagesCmd(jpgs, wPt, hPt, out)).then((_) => out);
  Future<String> addTextLayer(String pdfIn, String pdfOut, String fontPath, String json) =>
      _call(_AddLayerCmd(pdfIn, pdfOut, fontPath, json)).then((_) => pdfOut);
}

void _isolateMain(SendPort ready) {
  final core = ScannerCore.open();
  core.pdfInit(); // একবার — এই isolate সব PDFium state-এর মালিক
  final inbox = ReceivePort();
  ready.send(inbox.sendPort);

  inbox.listen((msg) {
    final req = msg as _Req;
    try {
      final b = core.b;
      final Object? result = switch (req.cmd) {
        _CountCmd c => _count(b, c.path),
        _ExtractCmd c => _extract(b, c),
        _CombineCmd c => _combine(b, c),
        _CompressCmd c => _compress(b, c),
        _FromImagesCmd c => _fromImages(b, c),
        _AddLayerCmd c => () { core.pdfAddTextLayer(c.pdfIn, c.pdfOut, c.fontPath, c.json); return c.pdfOut; }(),
      };
      req.reply.send(result);
    } catch (e) {
      req.reply.send('__err__:$e');
    }
  });
}

int _count(ScannerCoreBindings b, String path) {
  final p = path.toNativeUtf8();
  try { return b.sc_pdf_page_count(p.cast()); } finally { calloc.free(p); }
}

String _extract(ScannerCoreBindings b, _ExtractCmd c) {
  final cSrc = c.src.toNativeUtf8(), cOut = c.out.toNativeUtf8();
  final arr = calloc<Int32>(c.idx.length);
  for (var i = 0; i < c.idx.length; i++) arr[i] = c.idx[i];
  try {
    _ck(b.sc_pdf_extract(cSrc.cast(), arr, c.idx.length, cOut.cast()));
    return c.out;
  } finally { calloc.free(cSrc); calloc.free(cOut); calloc.free(arr); }
}

String _combine(ScannerCoreBindings b, _CombineCmd c) => _withStrArray(c.srcs, (arr) {
      final cOut = c.out.toNativeUtf8();
      try { _ck(b.sc_pdf_combine(arr, c.srcs.length, cOut.cast())); return c.out; }
      finally { calloc.free(cOut); }
    });

String _compress(ScannerCoreBindings b, _CompressCmd c) {
  final cSrc = c.src.toNativeUtf8(), cOut = c.out.toNativeUtf8();
  try { _ck(b.sc_pdf_compress(cSrc.cast(), c.dpi, c.q, cOut.cast())); return c.out; }
  finally { calloc.free(cSrc); calloc.free(cOut); }
}

String _fromImages(ScannerCoreBindings b, _FromImagesCmd c) => _withStrArray(c.jpgs, (arr) {
      final cOut = c.out.toNativeUtf8();
      try { _ck(b.sc_pdf_from_images(arr, c.jpgs.length, c.wPt, c.hPt, cOut.cast())); return c.out; }
      finally { calloc.free(cOut); }
    });

T _withStrArray<T>(List<String> items, T Function(Pointer<Pointer<Char>>) body) {
  final arr = calloc<Pointer<Char>>(items.length);
  final utfs = [for (final s in items) s.toNativeUtf8()];
  for (var i = 0; i < utfs.length; i++) arr[i] = utfs[i].cast();
  try { return body(arr); } finally {
    for (final u in utfs) calloc.free(u);
    calloc.free(arr);
  }
}

void _ck(ScStatus st) { if (st.code != 0) throw StateError('pdf native ${st.code}'); }
