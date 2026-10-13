import 'package:app/features/counter/presentation/notifiers/counter_notifier.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('10000 increments reach a listener within 250 ms', () {
    final container = ProviderContainer.test();
    int notified = 0;
    container.listen(counterProvider, (int? previous, int next) => notified = next);
    final notifier = container.read(counterProvider.notifier);

    final stopwatch = Stopwatch()..start();
    for (int i = 0; i < 10000; i++) {
      notifier.increment();
    }
    stopwatch.stop();

    expect(notified, 10000);
    expect(stopwatch.elapsedMilliseconds, lessThan(250));
  });
}
