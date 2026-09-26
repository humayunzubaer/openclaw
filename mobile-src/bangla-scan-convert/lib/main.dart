import 'package:flutter/material.dart';
import 'doc_store.dart';
import 'library/library_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final store = await DocStore.load(); // সব ডকুমেন্ট লোকাল JSON থেকে লোড
  runApp(BanglaScanApp(store: store));
}

class BanglaScanApp extends StatelessWidget {
  const BanglaScanApp({super.key, required this.store});
  final DocStore store;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Bangla Scan & Convert',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'NotoSansBengali',
        colorSchemeSeed: const Color(0xFF34357A),
      ),
      home: LibraryScreen(store: store),
    );
  }
}
