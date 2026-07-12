# Flutter E2E

- Official `integration_test` + project device/emulator runner = durable owner.
- Riverpod app → `$building-flutter-apps` owns Flutter commands, setup, selectors, logs, and source-of-truth checks.
- Non-Riverpod Flutter → existing project runner/docs; never invoke `$building-flutter-apps`.
- Test state/account/data = isolated; selectors = stable semantics/keys; assertion = visible outcome.
- Flutter integration tests drive Flutter UI; native OS surfaces outside Flutter's tree require platform automation or explicit manual evidence.
- Failure evidence = assertion + device/log/screenshot evidence.
