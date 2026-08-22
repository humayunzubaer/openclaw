import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app/app.dart';
import 'app/app_services_host.dart';
import 'app/background_guard.dart';
import 'app/lifecycle_observer.dart';
import 'app/providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final host = AppServicesHost(guard: const NoopBackgroundGuard());
  await host.ensureBooted();
  ScannerLifecycleObserver(host).attach(); // clean iOS detached disposal
  runApp(ProviderScope(
    overrides: [appServicesHostProvider.overrideWithValue(host)],
    child: const ScannerApp(),
  ));
}
