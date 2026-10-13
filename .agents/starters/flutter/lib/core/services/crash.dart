import 'dart:async';

abstract final class Crash {
  static Future<void> init({required FutureOr<void> Function() appRunner}) async {
    await appRunner();
  }
}
