/// Android foreground service / iOS BGProcessingTask-এর সাথে bridge।
/// Concrete implementation platform code-এ; backbone-এর শুধু begin/end দরকার।
abstract interface class BackgroundGuard {
  Future<void> begin(String message); // "Processing 42/100" notification দেখাবে
  Future<void> end();
}

class NoopBackgroundGuard implements BackgroundGuard {
  const NoopBackgroundGuard();
  @override
  Future<void> begin(String message) async {}
  @override
  Future<void> end() async {}
}
