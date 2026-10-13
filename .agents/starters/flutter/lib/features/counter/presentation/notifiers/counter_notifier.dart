import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'counter_notifier.g.dart';

@Riverpod(keepAlive: true)
class CounterNotifier extends _$CounterNotifier {
  @override
  int build() => 0;

  void increment() => state++;
}
