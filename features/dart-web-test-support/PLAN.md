# Cover forwarder-only web files and accept committed test-support packages

Status: Complete

## Outcome + scope

Fix [#184](https://github.com/sgaabdu4/hard-eng/issues/184). (1) The generated Flutter browser-test command compiles with `--dart2js-args=--disable-inlining`, so a web-only file made of one-line forwarders gets real LCOV lines instead of failing the coverage inventory; installed earlier forms upgrade. (2) A committed nested Dart package under a test path (`test/`, `tests/`, `__tests__/`) inside a parent Dart package, with its own lockfile, may be declared without `language` or `sources`; it then needs only lockfile and vulnerability checks, and fresh setup generates that group. Its Dart code is still formatted and analyzed by the parent's package-root gates. Non-goals: a "passing browser test counts as covered" exemption, running browser tests from a runner package automatically, lower thresholds.

## Repository context

Owners: `.hooks/project_setup.py` `browser_test_coverage` and its command constants (#158); `.hooks/gate_config.py` `validate_manifest_groups`, where language-less groups were accepted only for workspace roots; `setup.py` `gate_config`. Tests in `tests/test_setup.py` and `tests/test_package_discovery.py`.
Evidence (Dart 3.13.4, Chrome): a file with `objectUrl(...) => web.URL.createObjectURL(...)` and `revoke(...) => web.URL.revokeObjectURL(...)` called by a browser test → default `dart test -p chrome --coverage-path` records neither line; with `--dart2js-args=--disable-inlining` both appear as covered. An uncalled function stays absent either way. `--dart2js-args` is accepted though `dart test --help` does not list it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all open Hard Eng issues in one PR with proper testing and an adversarial review.
Decisions: Reuse the existing language-less group rules (lockfiles + vulnerabilities, inherited where applicable) as the proportionate set instead of a new package kind. Only an unmodified generated tests command is rewritten; a customized command stays with its owner, as in #158.

## Acceptance + steps

- [x] Generated browser command passes `--dart2js-args=--disable-inlining`; both earlier generated commands upgrade, custom commands stay → `test_flutter_browser_library_coverage_comes_from_browser_tests`.
- [x] Nested `test/…` package with a lockfile → fresh setup emits a group with only vulnerabilities + lockfiles (`dart pub get --enforce-lockfile`) and no language or sources, and validation accepts it; adding `sources` is rejected; omitting the group names the test-support option → `test_test_support_package_keeps_only_dependency_checks`.
- [x] No covering parent Dart package → the test-path package keeps its full product checks; a workspace-only root under `tests/` no longer aborts setup → `test_test_support_needs_a_covering_dart_parent`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Shared with [dart-root-analyzer-plugins](../dart-root-analyzer-plugins/PLAN.md#baseline--execution): unchanged `2aea113` → all gates PASS, 932 tests, 90.49% line coverage.
Execution: One builder at the existing owners.

## Risks + recovery

dart2js coverage stays source-map based: tree-shaken functions never appear, so browser percentages remain optimistic, and dead-code gates stay the control for unreached code. Disabling inlining changes only the browser test build. A test-support package's own tests must sit outside what the parent's `flutter test` collects, since the parent cannot resolve the runner's `package:test`. Projects that declare `depends_on` for affected checks should list the parent and the test-support package as depending on each other, so a change to either reruns both. Recovery: revert the commit.

## ux_reference

N/A — gate and setup behavior with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_setup.py tests/test_package_discovery.py` → 79 passed; Ruff, Pyrefly, Vulture and complexity checks clean. `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` → exit 0, all gates PASS.
Review: `/codex:adversarial-review --base main` found that the first version exempted any test-path package, even one with no parent to analyze it and in any language, and that a workspace-only root under a test path crashed setup with `KeyError: 'language'`. Both are repaired: test support now requires a covering parent Dart package, and the new regression fails on the earlier code with that `KeyError`.
E2E: Passed — synthetic Flutter app with a forwarder-only `lib/web_adapter.dart`, a `@TestOn('browser')` test and a committed `test/browser_runner` package with a lockfile, installed from this revision with real `setup.py`. Setup wrote the root `dart analyze --fatal-infos .` gate and a runner group with only vulnerabilities + lockfile. Through Hard Eng's `run_gate`: runner and root lockfile gates PASS; root types gate PASS clean, then FAIL on a type error planted in the runner's `lib/`. The tests gate with real `flutter test` and `dart test` on Chrome → `Line coverage: 4/4 (100.00%)`, `PASS tests`; the previous generated command on the same package → `FAIL tests: Coverage report omits production files: lib/web_adapter.dart`; rerunning setup upgraded that command to the new one.

Delivery target: Merge
Delivery: Passed — PR [#185](https://github.com/sgaabdu4/hard-eng/pull/185) checks green, squash-merged as `a2696f9`, main CI (Hard Eng, Dependency Graph) green on that commit; #183 and #184 closed.
