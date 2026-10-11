import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../bijoy/unicode_to_bijoy.dart';
import '../services/sutonny_font.dart';

/// Copy buttons for a Bangla result, plus a hint when SutonnyMJ is missing.
class OutputActions extends StatelessWidget {
  const OutputActions({
    super.key,
    required this.text,
    required this.font,
    required this.onOpenSettings,
  });

  final String text;
  final SutonnyFont font;
  final VoidCallback onOpenSettings;

  Future<void> _copy(BuildContext context, String value, String label) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text('$label কপি হয়েছে')));
  }

  @override
  Widget build(BuildContext context) {
    final enabled = text.trim().isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: enabled
                  ? () => _copy(
                      context,
                      unicodeToBijoy(text),
                      'বিজয় (SutonnyMJ) লেখা',
                    )
                  : null,
              icon: const Icon(Icons.copy),
              label: const Text('বিজয় কপি (SutonnyMJ)'),
            ),
            OutlinedButton.icon(
              onPressed: enabled
                  ? () => _copy(context, text, 'ইউনিকোড লেখা')
                  : null,
              icon: const Icon(Icons.copy_all),
              label: const Text('ইউনিকোড কপি'),
            ),
          ],
        ),
        ValueListenableBuilder<bool>(
          valueListenable: font.loaded,
          builder: (context, loaded, _) {
            if (loaded) return const SizedBox.shrink();
            return Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Card(
                color: Theme.of(context).colorScheme.tertiaryContainer,
                child: ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('SutonnyMJ ফন্ট যোগ করা হয়নি'),
                  subtitle: const Text(
                    'এখন সাধারণ বাংলা ফন্টে দেখানো হচ্ছে। হুবহু সুতন্বীএমজে-তে দেখতে ফন্ট যোগ করুন।',
                  ),
                  trailing: TextButton(
                    onPressed: onOpenSettings,
                    child: const Text('যোগ করুন'),
                  ),
                ),
              ),
            );
          },
        ),
      ],
    );
  }
}
