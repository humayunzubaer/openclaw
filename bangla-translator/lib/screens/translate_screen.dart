import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/sutonny_font.dart';
import '../services/translation_service.dart';
import '../widgets/bijoy_text.dart';
import '../widgets/output_actions.dart';

class TranslateScreen extends StatefulWidget {
  const TranslateScreen({
    super.key,
    required this.font,
    required this.translator,
    required this.onOpenSettings,
  });

  final SutonnyFont font;
  final TranslationService translator;
  final VoidCallback onOpenSettings;

  @override
  State<TranslateScreen> createState() => _TranslateScreenState();
}

class _TranslateScreenState extends State<TranslateScreen> {
  final _input = TextEditingController();
  var _source = SourceLanguage.english;
  var _result = '';
  var _busy = false;
  String? _error;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _translate() async {
    final text = _input.text;
    if (text.trim().isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.translator.translate(text, _source);
      if (!mounted) return;
      setState(() => _result = result);
    } on TranslationException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } on PlatformException catch (e) {
      if (!mounted) return;
      setState(() => _error = 'অনুবাদ করা যায়নি: ${e.message ?? e.code}');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final text = data?.text;
    if (text == null) return;
    _input.text = text;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('অফলাইন অনুবাদ', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'ইংরেজি বা রুশ থেকে বাংলা — ইন্টারনেট ছাড়াই',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        SegmentedButton<SourceLanguage>(
          segments: [
            for (final lang in SourceLanguage.values)
              ButtonSegment(
                value: lang,
                label: Text('${lang.nativeName} → বাংলা'),
              ),
          ],
          selected: {_source},
          onSelectionChanged: (s) => setState(() => _source = s.first),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _input,
          minLines: 5,
          maxLines: 12,
          decoration: InputDecoration(
            border: const OutlineInputBorder(),
            hintText: _source == SourceLanguage.english
                ? 'Type or paste English text…'
                : 'Введите или вставьте текст на русском…',
            suffixIcon: IconButton(
              tooltip: 'মুছুন',
              icon: const Icon(Icons.clear),
              onPressed: () => setState(() {
                _input.clear();
                _result = '';
                _error = null;
              }),
            ),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _busy ? null : _translate,
                icon: _busy
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.translate),
                label: const Text('অনুবাদ করুন'),
              ),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(
              onPressed: _paste,
              icon: const Icon(Icons.content_paste),
              label: const Text('পেস্ট'),
            ),
          ],
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Card(
            color: theme.colorScheme.errorContainer,
            child: ListTile(
              leading: const Icon(Icons.error_outline),
              title: Text(_error!),
              trailing: TextButton(
                onPressed: widget.onOpenSettings,
                child: const Text('প্যাক'),
              ),
            ),
          ),
        ],
        if (_result.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text('বাংলা অনুবাদ', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: BijoyText(_result, font: widget.font),
            ),
          ),
          const SizedBox(height: 8),
          OutputActions(
            text: _result,
            font: widget.font,
            onOpenSettings: widget.onOpenSettings,
          ),
        ],
      ],
    );
  }
}
