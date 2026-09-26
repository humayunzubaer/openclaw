import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/db/app_database.dart';
import 'app_services.dart';
import 'app_services_host.dart';

final appServicesHostProvider =
    Provider<AppServicesHost>((_) => throw UnimplementedError());

final appServicesProvider = FutureProvider<AppServices>((ref) =>
    ref.watch(appServicesHostProvider).ensureBooted());

/// Live document library.
final documentsProvider = StreamProvider<List<Document>>((ref) async* {
  final services = await ref.watch(appServicesProvider.future);
  yield* services.db.watchDocuments();
});
