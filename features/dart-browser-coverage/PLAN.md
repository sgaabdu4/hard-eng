# Cover browser-only Flutter libraries with browser-test LCOV

Status: Complete

## Outcome + scope

Fix [#158](https://github.com/sgaabdu4/hard-eng/issues/158): a Flutter package whose production Dart sources import browser-only libraries (`dart:js_interop`, `dart:html`, `package:web/` and similar) gets a tests gate that also runs its `@TestOn('browser')` tests with `dart test --platform=chrome --coverage-path` and appends that real LCOV to `coverage/lcov.info`, so passing browser tests satisfy the existing coverage inventory. Non-goals: classifying browser code as erased or counter-free, synthetic counters, lower thresholds, waivers, pure-Dart (`dart` manager) packages, CI provisioning.

## Repository context

Owners: `.hooks/project_setup.py` (`browser_test_coverage`, next to `strict_scanner_flags`), called for every package from `setup.py` installer loop so new and existing configs get it; inventory in `reports.line_coverage` is unchanged (`lcov_coverage` already merges duplicate `SF` records and resolves absolute `SF` paths). Test in `tests/test_setup.py`.
Evidence (synthetic package, Flutter 3.47.5 / Dart 3.13.4, Chrome): `flutter test --platform chrome --coverage` passes the test then exits 1 with no LCOV; `flutter_tools/lib/src/test/flutter_web_platform.dart` has no coverage support. `dart test -p chrome --coverage-path=…` (dart2js) writes LCOV with a `lib/web_adapter.dart` record, and an unexecuted `if` branch line reports `DA:…,0`. `--compiler=dart2wasm` writes an empty LCOV. `dart test -p chrome` on the whole `test/` directory fails because Flutter tests import `dart:ui`, so the browser run selects files whose `@TestOn` selector starts with `browser` or `chrome`; `@TestOn('!browser')` files are left to the VM run.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix all open Hard Eng issues, combine this with the #159 fix in one PR and decide the coverage trade-offs.
Trade-offs decided: accept dart2js source-map LCOV as the browser coverage producer and keep file-level inventory required. Do not infer uncovered functions from missing lines: on Dart 3.13.4, a test that called `revokeBlobUrl` (`=> web.URL.revokeObjectURL(url)`) and a one-statement block forwarder produced no lines for either, exactly like an uncalled function. With `--dart2js-args=-O0`, an uncalled function was still absent. `dart test` offers only dart2js and dart2wasm for Chrome, and dart2wasm wrote an empty report. Files made only of inlined forwarders keep failing rather than being exempted. The `sh -c` tests command follows the existing Dart format gate.
Consumer contract: browser tests carry `@TestOn('browser')` (so `flutter test` skips them), import `package:test/test.dart` rather than `flutter_test`, and the package declares `test` as a dev dependency; Chrome must be available. Only an unmodified template Flutter tests command is rewritten; a customized command is left to its owner.

## Acceptance + steps

- [x] Browser-importing Flutter package → tests gate runs the VM command, then `dart test --platform=chrome` on `@TestOn('browser')` files only (not `@TestOn('!browser')`), and the merged LCOV satisfies `line_coverage` with both runs' tests counted → `test_flutter_browser_library_coverage_comes_from_browser_tests`.
- [x] Package without browser imports → command unchanged; rewrite is idempotent → same test.
- [x] Real run: installed tests gate on the synthetic package → `Line coverage: 2/2`, `PASS tests`; a failing browser assertion → `Dart test failure: …`, `FAIL tests`; an added `@TestOn('!browser')` Flutter test → still `PASS tests`; no browser tests → stderr names the whole contract (annotation, `package:test` import, `test` dev dependency, Chrome) plus `Coverage report omits production files: lib/web_adapter.dart`.
- [x] Existing config with the old VM-only command → rerunning setup rewrites it identically to a fresh install.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Synthetic package, installed runner with the template command → `FAIL tests: Coverage report omits production files: lib/web_adapter.dart`; `flutter test --platform chrome --coverage --coverage-path=coverage/web.lcov` → test passes, exit 1, no file.
Execution: One builder; add the gate rewrite at the installer's package-migration owner and one focused test with stub `flutter`/`dart` executables.

## Risks + recovery

dart2js coverage is source-map based: tree-shaken functions never appear, interop-only lines have no mapping, and a file of only interop forwarders (`=> web.X(…)` or a one-statement block) gets no `SF` record and still fails the inventory; no branch records are produced. These make browser percentages optimistic, not fabricated; dead-code gates remain the control for unreached functions. Recovery: if Flutter's Chrome runner gains LCOV, replace the `dart test` step with it.

## ux_reference

N/A — hook-only change with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_setup.py` → 58 passed; with the LCOV append removed, or with a selector that also matches `@TestOn('!browser')`, the new test fails. Synthetic package runs as listed under Acceptance. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 804 tests passed.
E2E: Passed — `setup.py` installed into a synthetic Flutter package with `lib/web_adapter.dart`; Hard Eng's `run_gate` ran the rewritten tests gate with real `flutter test` and `dart test` on Chrome → `Line coverage: 2/2 (100.00%)`, `PASS tests`.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
