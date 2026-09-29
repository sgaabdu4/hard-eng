# Classify Dart declarations with a pinned analyzer

Status: Complete

## Outcome + scope

Dart coverage waives declaration-only libraries regardless of the consumer's analyzer: the classifier runs against a Hard Eng-owned, locked analyzer and fails with its real error instead of silently requiring every omitted file. `integration_test/` is treated as non-production source like `test/`. A shell script added after setup can no longer escape an explicit shellcheck file list. Non-goals: caching a compiled classifier, changing which declarations are erased, or changing the generated CI cache paths.

## Repository context

Owners: `.hooks/dart_coverage.py:erased_dart` (ran on the consumer's `.dart_tool/package_config.json` and returned an empty set on any failure), `.hooks/reports.py:line_coverage` (then reported "cover or mark" for declaration-only files), `.hooks/gate_config.py:nonproduction_source` (feeds `project_setup.adapt_sources` and `production_files`), `.hooks/update.py:scaffold_files` (the managed-file manifest: `.hooks/*.py` and `ruff.toml` only). `setup.configure_shellcheck` kept an existing shellcheck list unchanged and validation only required the role, so a later script went unchecked. A consumer pinned to analyzer 12 cannot compile the classifier (no `FormalParameterDefaultClause`), and a package without analyzer has no parser at all. `flutter test --coverage` never runs `integration_test/`, yet setup listed it as a production source. `dart analyze .` cannot exclude project files (`project_setup.validate_dart_exclusions`) and the Dart format gate's `git ls-files` lists `integration_test/` (`tests/test_dart_config.py`), so it stays analyzed and formatted like `test/`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user authorized this Hard Eng repair with one PR, guarded squash merge, verified main CI and a GitHub release following the previous release pattern. Consumers are described generically.

Pin: analyzer 14.4.0 (pub.dev latest). It compiles the current classifier (`FormalParameterDefaultClause`, `ClassDeclaration.body`) and its resolved lock floor is Dart 3.11.0, below Dart 3.13.0 shipped by Flutter 3.47.0, the oldest Flutter used by consumers' hosted CI. The manifest and lock ship as `.hooks/dart_declarations.pubspec.{yaml,lock}` so no consumer discovers a nested Dart package or analyzes the program; the classifier source stays embedded in Python and resolves in a temporary directory, offline from the shared pub cache first.

## Acceptance + steps

- [x] A consumer resolved to analyzer 12 keeps declaration-only files waived and real-code files required → extended `test_native_dart_declarations_and_runtime_controls`.
- [x] A consumer without analyzer keeps the same classification; an unrunnable classifier fails with its real cause and without "cover or mark" advice → extended `test_missing_dart_parser_keeps_sources_required`.
- [x] Real `dart test --coverage` on a package without a direct analyzer dependency still omits declaration-only libraries → `test_native_dart_lcov_omits_declaration_only_libraries` without an analyzer dependency.
- [x] `integration_test/` is excluded from production sources and kept with tests → extended `test_source_files_include_unexecuted_modules`.
- [x] The pinned manifest and lock reach consumers through the managed-file manifest → Dart install in `test_plain_dart_uses_native_coverage_tool`; Hard Eng's vulnerability gate scans the lock.
- [x] A new script missing from an explicit shellcheck list fails the check by name, and rerunning setup appends it → extended `test_new_repository_inputs_require_applicable_gates`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base origin/main`.

## Baseline + execution

Result: Passed
Evidence: `PYTEST_XDIST_AUTO_NUM_WORKERS=4 python3 .hooks/hard-eng.py check` on unchanged `7eebdaf3` → all 17 gates PASS, 1086 tests, 90.57% line coverage, 3 min 9 s.
Execution: One builder; classifier and manifest first, then `integration_test`, then the integrated gate.

## Risks + recovery

Cold CI runs download the pinned analyzer (measured 5.3 s, 56 MB) only when a Dart file is missing from LCOV; warm runs resolve offline in 0.6 s. The generated workflow does not cache the pub cache; adding that needs a workflow migration outside this change. Consumer syntax newer than analyzer 14.4 parses with errors and stays required, the safe direction. Recovery: revert the classifier commit.

## ux_reference

N/A — coverage validation has no product UI.

## Verification

Result: Passed
Evidence: The pre-fix classifier returned no waiver for a consumer resolved to analyzer 12.1.0; the pinned classifier waived the same declaration-only file. Focused Dart coverage, report, runner, setup, update, adoption, package-discovery and Husky suites passed (293 and 312 tests, four workers); the native analyzer-12 fixture takes 53 s, including its own pub get. The integrated Ready run passed 1086 tests (90.52% line coverage) and every gate except one new complexity finding in `validate_required_checks`, repaired by extracting the shell-list check; Ruff and Pyrefly then passed with 0 diagnostics. osv-scanner parses the pinned lock (18 packages, 0 vulnerabilities). The final Complete `python3 .hooks/hard-eng.py check --base origin/main` passed all 17 gates in 2 min 17 s: 1086 tests in 99.8 s with four workers, 90.53% line coverage.
E2E: N/A — no user journey; native `dart pub get`, `dart test --coverage` and the classifier run in the fixtures exercise the real command boundary.

Delivery target: Merge
Delivery: Pending — PR CI, guarded squash merge, merged-main CI and GitHub release.
