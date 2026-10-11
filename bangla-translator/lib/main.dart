import 'package:flutter/material.dart';

import 'screens/converter_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/translate_screen.dart';
import 'services/sutonny_font.dart';
import 'services/translation_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final font = SutonnyFont();
  await font.init();
  runApp(BanglaTranslatorApp(font: font, translator: TranslationService()));
}

class BanglaTranslatorApp extends StatelessWidget {
  const BanglaTranslatorApp({
    super.key,
    required this.font,
    required this.translator,
  });

  final SutonnyFont font;
  final TranslationService translator;

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF006A4E); // Bangladesh flag green
    return MaterialApp(
      title: 'বাংলা অনুবাদক',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, useMaterial3: true),
      darkTheme: ThemeData(
        colorSchemeSeed: seed,
        brightness: Brightness.dark,
        useMaterial3: true,
      ),
      home: HomeScreen(font: font, translator: translator),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.font, required this.translator});

  final SutonnyFont font;
  final TranslationService translator;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _tab = 0;

  void _openSettings() => setState(() => _tab = 2);

  @override
  void dispose() {
    widget.translator.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      TranslateScreen(
        font: widget.font,
        translator: widget.translator,
        onOpenSettings: _openSettings,
      ),
      ConverterScreen(font: widget.font, onOpenSettings: _openSettings),
      SettingsScreen(font: widget.font, translator: widget.translator),
    ];
    return Scaffold(
      body: SafeArea(
        child: IndexedStack(index: _tab, children: pages),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.translate), label: 'অনুবাদ'),
          NavigationDestination(
            icon: Icon(Icons.font_download_outlined),
            label: 'ফন্ট রূপান্তর',
          ),
          NavigationDestination(
            icon: Icon(Icons.download_for_offline_outlined),
            label: 'প্যাক ও ফন্ট',
          ),
        ],
      ),
    );
  }
}
