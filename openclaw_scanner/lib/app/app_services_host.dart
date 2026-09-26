import 'package:flutter/foundation.dart';
import 'app_config.dart';
import 'app_services.dart';
import 'background_guard.dart';

/// বর্তমান AppServices ধরে রাখে; iOS detached→resumed cycle-এ native handle leak
/// ছাড়াই tear down / আবার boot করতে পারে।
class AppServicesHost extends ChangeNotifier {
  AppServicesHost({required this.guard, this.config = const AppConfig()});
  final BackgroundGuard guard;
  final AppConfig config;

  AppServices? _services;
  Future<AppServices>? _booting;
  bool _disposing = false;

  AppServices get require =>
      _services ?? (throw StateError('AppServices not booted'));
  bool get isBooted => _services != null;

  Future<AppServices> ensureBooted() async {
    if (_services != null) return _services!;
    return _booting ??= _boot();
  }

  Future<AppServices> _boot() async {
    final s = await AppServices.boot(backgroundGuard: guard, config: config);
    _services = s;
    _booting = null;
    notifyListeners();
    return s;
  }

  /// Graceful, best-effort teardown. Integrity এর জন্য এটা শেষ হওয়া জরুরি নয় —
  /// প্রতিটা write transaction, তাই truncated shutdown-ও DB consistent রাখে।
  Future<void> shutdown() async {
    if (_disposing || _services == null) return;
    _disposing = true;
    final s = _services;
    _services = null;
    notifyListeners();
    try {
      await s?.dispose();
    } finally {
      _disposing = false;
    }
  }
}
