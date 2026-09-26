import 'dart:io';
import 'package:flutter/material.dart';
import 'reflow.dart';
import 'text_block_model.dart';

class InScanTextEditor extends StatefulWidget {
  const InScanTextEditor({
    super.key,
    required this.imageFile,
    required this.imageWidthPx,
    required this.imageHeightPx,
    required this.blocks,
    required this.onSave,
    this.shrinkToFit = true,
  });

  final File imageFile;
  final double imageWidthPx, imageHeightPx;
  final List<EditableTextBlock> blocks;
  final ValueChanged<List<EditableTextBlock>> onSave;
  final bool shrinkToFit;

  @override
  State<InScanTextEditor> createState() => _InScanTextEditorState();
}

class _InScanTextEditorState extends State<InScanTextEditor> {
  late final Map<String, TextEditingController> _controllers = {
    for (final b in widget.blocks) b.id: TextEditingController(text: b.text),
  };
  String? _selectedId;

  EditableTextBlock? get _selected =>
      widget.blocks.where((b) => b.id == _selectedId).firstOrNull;

  @override
  void dispose() {
    for (final c in _controllers.values) c.dispose();
    super.dispose();
  }

  void _setAlign(TextAlignH a) {
    final b = _selected;
    if (b == null) return;
    setState(() => b.align = a);
  }

  void _save() {
    for (final b in widget.blocks) b.text = _controllers[b.id]!.text;
    widget.onSave(widget.blocks);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('টেক্সট এডিট'),
        actions: [IconButton(onPressed: _save, icon: const Icon(Icons.check))],
      ),
      body: InteractiveViewer(
        maxScale: 8,
        child: SizedBox(
          width: widget.imageWidthPx,
          height: widget.imageHeightPx,
          child: Stack(children: [
            Positioned.fill(child: Image.file(widget.imageFile, fit: BoxFit.fill)),
            for (final b in widget.blocks) _blockField(b),
          ]),
        ),
      ),
      bottomNavigationBar: _selected == null
          ? null
          : Padding(
              padding: const EdgeInsets.all(12),
              child: SegmentedButton<TextAlignH>(
                segments: const [
                  ButtonSegment(value: TextAlignH.left, icon: Icon(Icons.format_align_left)),
                  ButtonSegment(value: TextAlignH.center, icon: Icon(Icons.format_align_center)),
                  ButtonSegment(value: TextAlignH.right, icon: Icon(Icons.format_align_right)),
                ],
                selected: {_selected!.align},
                onSelectionChanged: (s) => _setAlign(s.first),
              ),
            ),
    );
  }

  Widget _blockField(EditableTextBlock b) {
    final leftPx = b.rectN.left * widget.imageWidthPx;
    final topPx = b.rectN.top * widget.imageHeightPx;
    final widthPx = b.rectN.width * widget.imageWidthPx;
    final baseFontPx = b.fontSizeN * widget.imageHeightPx;
    final maxHeightPx = b.rectN.height * widget.imageHeightPx;

    final fit = fitText(
      text: _controllers[b.id]!.text,
      maxWidthPx: widthPx,
      baseFontPx: baseFontPx,
      maxHeightPx: maxHeightPx,
      shrinkToFit: widget.shrinkToFit,
    );

    return Positioned(
      left: leftPx,
      top: topPx,
      width: widthPx,
      height: fit.height.clamp(maxHeightPx, double.infinity),
      child: GestureDetector(
        onTap: () => setState(() => _selectedId = b.id),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.92),
            border: _selectedId == b.id
                ? Border.all(color: Theme.of(context).colorScheme.primary, width: 2)
                : null,
          ),
          child: TextField(
            controller: _controllers[b.id],
            onChanged: (_) => setState(() {}),
            maxLines: null,
            textAlign: switch (b.align) {
              TextAlignH.center => TextAlign.center,
              TextAlignH.right => TextAlign.right,
              TextAlignH.left => TextAlign.left,
            },
            style: bengaliStyle(fit.fontSizePx),
            strutStyle: StrutStyle(fontSize: fit.fontSizePx, height: 1.42, forceStrutHeight: true),
            decoration: const InputDecoration.collapsed(hintText: ''),
            keyboardType: TextInputType.multiline,
          ),
        ),
      ),
    );
  }
}
