# Measure Flutter package Dart sources outside lib/

Status: Complete

## Outcome + scope

A Flutter package whose production `sources` include Dart outside `lib/` (for example a root `scripts/` CLI) gets a tests gate that also runs the tests importing those files under `dart test --coverage` on the Dart VM and appends their LCOV, so the files count toward the inventory and the 70% line minimum. A file outside `lib/` that no test reaches still fails the inventory by name, with the test contract on stderr. Non-goals: excluding such files, lowering thresholds, pure-Dart (`dart` manager) packages, customized tests commands.

## Repository context

Owners: `.hooks/project_setup.py` generated Flutter tests commands (`FLUTTER_TESTS`, `BROWSER_TESTS`, `browser_test_coverage`), called for every package from the `setup.py` installer loop (new step runs from `setup.configure_dart`); `sources` come from `project_setup.adapt_sources` (first path part of every non-test Dart file) and `reports.line_coverage` requires each of them in `coverage/lcov.info`, unchanged here. Precedents: #158 and #184 added a `dart test --platform=chrome` run whose LCOV is appended for browser-only libraries.
Evidence (Flutter 3.47.5, Dart 3.13.4): `flutter test --coverage` passes `libraryNames` to `coverage.collect` as scoped output, and `includesScript` keeps only `package:` URIs, so a `file:` script imported by a test can never appear; `--coverage-package` matches package names only. `dart test --coverage-path` is scoped the same way (`_filterCoveragePackages`). `dart test --coverage=<dir>` (JSON workflow) reports every library by design, and `dart run coverage:format_coverage --lcov --check-ignore --report-on=scripts --base-directory=.` turns it into `SF:scripts/check_coverage.dart`. `coverage` resolves through `test` → `test_core` and runs with empty stderr.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user authorized this Hard Eng repair with one PR, guarded squash merge, verified main CI and a GitHub release following the previous release pattern. Consumers are described generically.

Measure, not exclude: the VM JSON workflow is the supported producer for files outside `lib/`. Tests are selected by their relative imports of the non-`lib` source names baked in at setup; the VM step runs before the browser step, whose no-test branch exits. Consumer contract: such tests import the file by relative path and `package:test/test.dart` (not `flutter_test`), with `test` as a dev dependency. Only an unmodified generated command is rewritten; a customized one is left to its owner.

## Acceptance + steps

- [x] Flutter package with `lib` and `scripts` sources → tests gate runs Flutter's VM command, then `dart test --coverage=coverage/vm` on only the tests importing `scripts/`, formats `--report-on=scripts`, appends to `coverage/lcov.info`; merged report satisfies `line_coverage`; rewrite is idempotent, combines with the browser step, and leaves `lib`-only packages and custom commands unchanged → `test_only_generated_flutter_commands_gain_dart_vm_coverage` and `test_flutter_dart_outside_lib_is_measured_on_the_dart_vm` in `tests/test_dart_coverage.py`.
- [x] No test imports the non-`lib` sources → stderr names the contract, the gate continues, and the inventory reports the omitted file → same test.
- [x] Real run: installer into a synthetic Flutter package with `scripts/check_coverage.dart` and a relative-import test → `run_gate` shows the script's lines in the report and `Line coverage` counted against 70%, `PASS tests`; without the script's test → contract on stderr, `Coverage report omits production files: scripts/check_coverage.dart`, `FAIL tests`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base origin/main`.

## Baseline + execution

Result: Passed
Evidence: `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `aa66e749` → all 17 gates PASS, 1086 tests, 90.53% line coverage, 162 s. Installer at `aa66e749` into the synthetic Flutter package, real `run_gate` on its tests gate → `FAIL tests: Coverage report omits production files: scripts/check_coverage.dart` although the script's tests passed.
Execution: One builder; generator + focused test first, then the synthetic E2E, then the integrated gate.

## Risks + recovery

Tests of non-`lib` sources run twice (Flutter VM run and `dart test`); both are the package's own tests and the selection is limited to files importing those sources. A test written with `flutter_test` fails to compile under `dart test`, which fails the gate loudly with the compiler error. Pure-Dart packages use `coverage:test_with_coverage`, also package-scoped, so their non-`lib` sources remain a known separate gap. Recovery: revert the generator commit; existing installs keep a customized command untouched.

## ux_reference

N/A — generated gate command with no product UI.

## Verification

Result: Passed
Evidence: Focused test passes; it fails when the stale `coverage/vm` removal, the LCOV append, the `*_test.dart` filter or the rewrite is removed. Existing-install migration: `setup.py --plan --previous-source <aa66e749 export>` over the old install rewrites the tests command identically to a fresh install. Setup calls the rewrite from `setup.configure_dart`, keeping `plan_install` within the statement limit. Final `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0, all 17 gates PASS, 1088 tests in 173 s, 90.56% line coverage, 203 s total.
E2E: Passed — installer into a synthetic Flutter package (`lib/app.dart`, `scripts/check_coverage.dart`, `test/check_coverage_test.dart` importing `../scripts/check_coverage.dart` with `package:test`), real `run_gate` with real `flutter test`, `dart test` and `format_coverage` → `SF:scripts/check_coverage.dart LF:9 LH:7`, `Line coverage: 8/10 (80.00%; minimum 70%)`, `PASS tests` in 4.5 s. Weaker script test → `Line coverage: 4/10 (40.00%)`, `FAIL tests: Line coverage is below the required 70%`. No script test → stderr contract plus `FAIL tests: Coverage report omits production files: scripts/check_coverage.dart`. An added untested `scripts/untested.dart` beside the tested script → `FAIL tests: Coverage report omits production files: scripts/untested.dart`.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green on the merged SHA, GitHub release.
