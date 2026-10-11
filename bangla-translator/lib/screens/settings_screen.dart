import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/sutonny_font.dart';
import '../services/translation_service.dart';
import '../widgets/bijoy_text.dart';

/// Offline language packs and the SutonnyMJ font.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.font,
    required this.translator,
  });

  final SutonnyFont font;
  final TranslationService translator;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _downloaded = <LanguagePack, bool>{};
  final _working = <LanguagePack>{};
  var _wifiOnly = false;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    for (final pack in LanguagePack.values) {
      try {
        final ok = await widget.translator.isDownloaded(pack);
        if (mounted) setState(() => _downloaded[pack] = ok);
      } on PlatformException {
        // Status stays unknown; the user can still tap download.
      }
    }
  }

  void _show(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _run(LanguagePack pack, Future<void> Function() action) async {
    setState(() => _working.add(pack));
    try {
      await action();
    } on TranslationException catch (e) {
      _show(e.message);
    } on PlatformException catch (e) {
      _show('সমস্যা হয়েছে: ${e.message ?? e.code}');
    } finally {
      if (mounted) setState(() => _working.remove(pack));
      await _refresh();
    }
  }

  Future<void> _downloadAll() async {
    for (final pack in LanguagePack.values) {
      if (_downloaded[pack] == true) continue;
      await _run(
        pack,
        () => widget.translator.download(pack, wifiOnly: _wifiOnly),
      );
    }
  }

  Future<void> _importFont() async {
    final picked = await FilePicker.pickFile(
      dialogTitle: 'SutonnyMJ.ttf বেছে নিন',
    );
    if (picked == null) return;
    try {
      final bytes = await picked.xFile.readAsBytes();
      await widget.font.import(bytes);
      _show('SutonnyMJ ফন্ট যোগ হয়েছে');
    } on FormatException catch (e) {
      _show(e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final allReady = LanguagePack.values.every((p) => _downloaded[p] == true);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('অফলাইন ভাষার প্যাক', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'প্রতিটি প্যাক প্রায় ৩০ MB। একবার ইন্টারনেট দিয়ে নামালে এরপর অনুবাদে আর ইন্টারনেট লাগবে না।',
          style: theme.textTheme.bodyMedium,
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('শুধু Wi-Fi দিয়ে নামাও'),
          value: _wifiOnly,
          onChanged: (v) => setState(() => _wifiOnly = v),
        ),
        for (final pack in LanguagePack.values) _packTile(pack),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: allReady || _working.isNotEmpty ? null : _downloadAll,
          icon: const Icon(Icons.download),
          label: Text(allReady ? 'সব প্যাক নামানো আছে' : 'সব প্যাক নামাও'),
        ),
        const Divider(height: 40),
        Text('SutonnyMJ ফন্ট', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'SutonnyMJ একটি লাইসেন্সকৃত ফন্ট, তাই অ্যাপের সাথে দেওয়া হয়নি। '
          'আপনার কম্পিউটারের C:\\Windows\\Fonts থেকে SutonnyMJ.ttf ফোনে এনে এখানে যোগ করুন।',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        ValueListenableBuilder<bool>(
          valueListenable: widget.font.loaded,
          builder: (context, loaded, _) => Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Icon(
                        loaded ? Icons.check_circle : Icons.error_outline,
                        color: loaded ? Colors.green : theme.colorScheme.error,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          loaded ? 'ফন্ট চালু আছে' : 'ফন্ট যোগ করা হয়নি',
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  BijoyText(
                    'নমুনা: গণপ্রজাতন্ত্রী বাংলাদেশ সরকার',
                    font: widget.font,
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: _importFont,
                    icon: const Icon(Icons.font_download),
                    label: Text(
                      loaded ? 'অন্য ফাইল দিন' : 'SutonnyMJ.ttf যোগ করুন',
                    ),
                  ),
                  if (loaded)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        'নতুন ফাইল দিলে অ্যাপ আবার খোলার পর চালু হবে।',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _packTile(LanguagePack pack) {
    final working = _working.contains(pack);
    final downloaded = _downloaded[pack];
    final status = switch (downloaded) {
      true => 'নামানো আছে — অফলাইনে কাজ করবে',
      false => 'নামানো হয়নি',
      null => 'যাচাই করা হচ্ছে…',
    };
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        downloaded == true ? Icons.offline_pin : Icons.cloud_download_outlined,
        color: downloaded == true ? Colors.green : null,
      ),
      title: Text(pack.banglaName),
      subtitle: Text(status),
      trailing: working
          ? const SizedBox.square(
              dimension: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : downloaded == true
          ? IconButton(
              tooltip: 'মুছে ফেলুন',
              icon: const Icon(Icons.delete_outline),
              onPressed: () => _run(pack, () => widget.translator.delete(pack)),
            )
          : IconButton(
              tooltip: 'নামাও',
              icon: const Icon(Icons.download),
              onPressed: () => _run(
                pack,
                () => widget.translator.download(pack, wifiOnly: _wifiOnly),
              ),
            ),
    );
  }
}
