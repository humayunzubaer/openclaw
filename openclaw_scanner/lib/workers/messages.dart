import 'dart:isolate';

sealed class PoolMessage {}
class WorkerReady extends PoolMessage {
  WorkerReady(this.id, this.control);
  final int id;
  final SendPort control;
}
class WorkerStopped extends PoolMessage {
  WorkerStopped(this.id);
  final int id;
}
// Control messages (pool → worker) plain string: 'wake' | 'stop'.
