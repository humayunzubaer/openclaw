import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import '../library/library_screen.dart';

class ScannerApp extends StatelessWidget {
  const ScannerApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OpenClaw Scanner',
      debugShowCheckedModeBanner: false,
      // Noto Sans Bengali app-wide → সব Bengali label-এ যুক্তবর্ণ ঠিকমতো render হবে।
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'NotoSansBengali',
        colorSchemeSeed: const Color(0xFF34357A),
      ),
      supportedLocales: const [Locale('bn'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const LibraryScreen(),
    );
  }
}
