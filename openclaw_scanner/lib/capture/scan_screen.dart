import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app/providers.dart';
import '../data/db/converters.dart';
import 'scan_controller.dart';

class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({super.key});
  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen> {
  ScanController? _c;
  CaptureMode _mode = CaptureMode.document;
  int _pages = 0;

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final services = await ref.read(appServicesProvider.future);
      final c = ScanController(services);
      await c.init();
      await c.startDocument('Scan ${DateTime.now()}');
      if (mounted) setState(() => _c = c);
    });
  }

  @override
  void dispose() { _c?.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final c = _c;
    if (c == null) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      appBar: AppBar(title: Text('স্ক্যান ($_pages পৃষ্ঠা)')),
      body: Column(children: [
        Expanded(child: CameraPreview(c.camera)),
        SegmentedButton<CaptureMode>(
          segments: const [
            ButtonSegment(value: CaptureMode.document, label: Text('ডকুমেন্ট')),
            ButtonSegment(value: CaptureMode.book, label: Text('বই')),
            ButtonSegment(value: CaptureMode.idCard, label: Text('আইডি')),
            ButtonSegment(value: CaptureMode.businessCard, label: Text('কার্ড')),
          ],
          selected: {_mode},
          onSelectionChanged: (s) => setState(() => _mode = s.first),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
            FilledButton.icon(
              onPressed: () async { await c.capturePage(_mode); setState(() => _pages++); },
              icon: const Icon(Icons.camera), label: const Text('ক্যাপচার')),
            OutlinedButton.icon(
              onPressed: () async {
                await c.finishAndOcr();
                if (context.mounted) Navigator.pop(context);
              },
              icon: const Icon(Icons.check), label: const Text('OCR শুরু')),
          ]),
        ),
      ]),
    );
  }
}
