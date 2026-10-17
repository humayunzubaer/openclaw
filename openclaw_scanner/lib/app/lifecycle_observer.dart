import 'package:flutter/widgets.dart';
import 'app_services_host.dart';

class ScannerLifecycleObserver with WidgetsBindingObserver {
  ScannerLifecycleObserver(this._host);
  final AppServicesHost _host;

  void attach() => WidgetsBinding.instance.addObserver(this);
  void detach() => WidgetsBinding.instance.removeObserver(this);

  @override
  Future<void> didChangeAppLifecycleState(AppLifecycleState state) async {
    switch (state) {
      case AppLifecycleState.resumed:
        await _host.ensureBooted();
      case AppLifecycleState.detached:
        // App terminating — in-flight batch write drain + DriftIsolate close।
        await _host.shutdown().timeout(
          const Duration(seconds: 3),
          onTimeout: () {}, // transaction atomicity already guarantees integrity
        );
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
      case AppLifecycleState.hidden:
        // dispose করব না — BackgroundGuard batch চালু রাখে।
        break;
    }
  }
}
