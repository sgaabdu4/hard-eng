# Measure pure-Dart sources outside lib/ and tolerate raw stdout in Dart reports

Status: Complete

## Outcome + scope

A pure-Dart (`dart` manager) package whose production `sources` include Dart outside `lib/` gets a tests gate that, after `coverage:test_with_coverage`, runs the tests importing those files under `dart test --coverage` and appends their LCOV, so the files count toward the inventory and the 70% line minimum; an untested file outside `lib/` still fails the inventory by name. The Dart test report reader skips lines that are not reporter events (raw stdout from a test) and still reads every event, so a failing test is still reported as failing. dart-decimate stays on the latest release. Non-goals: excluding such files, lowering thresholds, customized tests commands, pinning scanner versions.

## Repository context

Owners: `.hooks/project_setup.py` `adapt_package` (pure-Dart tests command) and `outside_lib_coverage` / `run_vm_tests` (#212's Dart VM step, called from `setup.configure_dart` for every Dart package); `setup.configure_dart` also detects `coverage:test_with_coverage` for its analysis-options marker. `.hooks/dart_test_report.py` `dart_events`, read by `reports.completed_tests` and `failure_summary`. dart-decimate: `tool_setup.provision_tools` installs `npm:dart-decimate@latest` with a zero remote-version cache (DECISION.md, strict scanner gates); no version is pinned anywhere in the repository.
Evidence (Dart 3.13.4, coverage 1.15.1): `test_with_coverage` always passes `--scope-output` (package names) to `collect`, and `includesScript` keeps only `package:` URIs, so a relative-imported `scripts/` file can never appear in its LCOV.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user authorized one Hard Eng PR, squash merge, verified main CI, a GitHub release following the previous pattern and remote branch deletion. Consumers are described generically.

Measure, not exclude: reuse #212's VM step unchanged for the pure-Dart command, same consumer contract (relative import + `package:test`). Report reader: an event is a JSON object or list of objects; any other line is test output and is skipped. Failures stay visible because `completed_tests` still requires a final `done` event with `success: true` and `failure_summary` still reads every `testDone`. dart-decimate: keep the `@latest` policy; confirm the provisioned version is the newest published one instead of adding a pin.

## Acceptance + steps

- [x] Pure-Dart package with `lib` and `scripts` sources → tests command runs `test_with_coverage`, then the VM step on tests importing `scripts/`, appending to `coverage/lcov.info`; idempotent; `lib`-only commands unchanged → `test_pure_dart_outside_lib_is_measured_after_test_with_coverage` in `tests/test_dart_coverage.py`; setup still writes the coverage marker for the wrapped command → `test_plain_dart_uses_native_coverage_tool` in `tests/test_setup.py` (its `test_driver/` source now gets the VM step).
- [x] Real run: installer into a synthetic pure-Dart package with a tested `scripts/check.dart` → `run_gate` counts the script against 70% and passes; an added untested `scripts/untested.dart` → `FAIL tests` naming it.
- [x] Raw non-JSON lines in a Dart report → passing run still counts its tests; failing run still fails `completed_tests` and `failure_summary` names the failing test → test in `tests/test_reports.py`.
- [x] dart-decimate → `npm view dart-decimate version` matches the version `mise` provisions from `npm:dart-decimate@latest`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base origin/main`.

## Baseline + execution

Result: Passed
Evidence: `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `6eba8cb1` → exit 0, 1088 tests in 175 s, 232 s total (an earlier attempt under load average ~50 hit the 300 s tests timeout). Installer at `6eba8cb1` into the synthetic pure-Dart package, real `run_gate` → both tests pass, then `FAIL tests: Coverage report omits production files: scripts/check.dart` (an inventory failure no test can fix).
Execution: One builder; generator + reader changes with focused tests, then the synthetic E2E, then the integrated gate.

## Risks + recovery

Tests of non-`lib` sources run twice in pure-Dart packages, as #212 accepted for Flutter. Skipping non-event lines could hide a truncated report; the final `done`/`success` requirement keeps that a failure. Recovery: revert the commit; customized commands are untouched.

## ux_reference

N/A — generated gate command and report reader with no product UI.

## Verification

Result: Passed
Evidence: Focused tests pass (179 in the three affected files). Red checks: without the pure-Dart rewrite entry the focused test fails (no `dart test` run); with the old `setup.py` marker check the install test loses the marker; with the old reader the raw-output test fails with `JSONDecodeError`. `npm view dart-decimate version` → 0.0.63 and `tool_setup.provision_batch` for `npm:dart-decimate@latest` provisions `dart-decimate 0.0.63`; no pin exists to bump. Final `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0, 1090 tests in 290 s under load, 90.63% line coverage, 328 s total.
E2E: Passed — installer into a synthetic pure-Dart package (`lib/app.dart`, `scripts/check.dart`, `test/check_test.dart` importing `../scripts/check.dart`), real `run_gate` with real `test_with_coverage`, `dart test` and `format_coverage` → `SF:scripts/check.dart LF:4 LH:4`, `Line coverage: 6/6 (100.00%; minimum 70%)`, `PASS tests`. Weaker script test → `Line coverage: 4/6 (66.67%)`, `FAIL tests: Line coverage is below the required 70%`. Added untested `scripts/untested.dart` → `FAIL tests: Coverage report omits production files: scripts/untested.dart`.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green on the merged SHA, GitHub release.
