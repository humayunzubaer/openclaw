import 'package:flutter/material.dart';

import '../services/sutonny_font.dart';
import '../widgets/bijoy_text.dart';
import '../widgets/output_actions.dart';

/// Converts any Unicode Bangla text to Bijoy (SutonnyMJ) without translating.
class ConverterScreen extends StatefulWidget {
  const ConverterScreen({
    super.key,
    required this.font,
    required this.onOpenSettings,
  });

  final SutonnyFont font;
  final VoidCallback onOpenSettings;

  @override
  State<ConverterScreen> createState() => _ConverterScreenState();
}

class _ConverterScreenState extends State<ConverterScreen> {
  final _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('ইউনিকোড → সুতন্বীএমজে', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'ইউনিকোড বাংলা লিখুন বা পেস্ট করুন; বিজয় (ANSI) লেখা কপি করে Word-এ SutonnyMJ ফন্টে বসান।',
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _input,
          minLines: 4,
          maxLines: 10,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            border: const OutlineInputBorder(),
            hintText: 'যেমন: গণপ্রজাতন্ত্রী বাংলাদেশ সরকার',
            suffixIcon: IconButton(
              tooltip: 'মুছুন',
              icon: const Icon(Icons.clear),
              onPressed: () => setState(_input.clear),
            ),
          ),
        ),
        if (_input.text.trim().isNotEmpty) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: BijoyText(_input.text, font: widget.font),
            ),
          ),
          const SizedBox(height: 8),
          OutputActions(
            text: _input.text,
            font: widget.font,
            onOpenSettings: widget.onOpenSettings,
          ),
        ],
      ],
    );
  }
}
