import 'package:bangla_translator/screens/converter_screen.dart';
import 'package:bangla_translator/services/sutonny_font.dart';
import 'package:bangla_translator/services/translation_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('converter shows Unicode text until SutonnyMJ is loaded', (
    tester,
  ) async {
    final font = SutonnyFont();
    String? copied;
    final messenger = tester.binding.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        copied = (call.arguments as Map)['text'] as String?;
      }
      return null;
    });
    addTearDown(
      () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ConverterScreen(font: font, onOpenSettings: () {}),
        ),
      ),
    );
    await tester.enterText(find.byType(TextField), 'বাংলাদেশ');
    await tester.pump();

    expect(find.text('বাংলাদেশ'), findsWidgets);
    expect(find.text('SutonnyMJ ফন্ট যোগ করা হয়নি'), findsOneWidget);

    await tester.tap(find.text('বিজয় কপি (SutonnyMJ)'));
    await tester.pump();
    expect(copied, 'evsjv‡`k');
  });

  test('isFontFile accepts TrueType and rejects other files', () {
    expect(isFontFile(Uint8List.fromList([0, 1, 0, 0, 9])), isTrue);
    expect(isFontFile(Uint8List.fromList('OTTO'.codeUnits)), isTrue);
    expect(isFontFile(Uint8List.fromList('%PDF'.codeUnits)), isFalse);
  });

  test('long lines are split at sentence ends', () {
    final line = List.filled(30, 'This is a sentence.').join(' ');
    final chunks = splitForTranslation(line, maxLength: 100);
    expect(chunks.length, greaterThan(1));
    expect(chunks.every((c) => c.length <= 100), isTrue);
    expect(chunks.join(' '), line);
  });
}
