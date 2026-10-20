# Python greenfield setup

Status: Complete

## Outcome + scope

A new uv app (`uv init --app`) with Hard Eng installed can pass every check after an agent adds a function, its tests and a performance test. The release canary found seven faults on `develop` 3620a68. No check becomes weaker: each fix tells an empty scope from a real gap, or names the rule that fails. Non-goals: brownfield adoption of old findings (a separate decision), and the same source-drift check for JavaScript and Dart.

## Repository context

Owners: `.hooks/hard-eng.py` and `.hooks/reports.py` run gates and check their reports. `setup.py` and the new `.hooks/python_setup.py` adapt Python packages. `.hooks/gate_config.py` checks the configuration. The new `.hooks/change_size.py` holds the size rules from `plans.py`. Four of these files were at the 1000-line limit (HE-FILE-LENGTH), so code moved into the two new modules.
Same cause: one cause, an empty or missing scope that a gate reads as a failure, gave five faults: no performance folder, jscpd skips small files, OSV finds no package, Import Linter matches no submodule, and no branch point without a remote. Searched the other report checks for the same case: the Bun lockfile case already had a fix (`empty_bun`), and Semgrep, Gitleaks and coverage scan files that always exist in a package. The source-drift fault has a Swift fix already (`swift_setup.unscanned`); JavaScript and Dart have the same gap and are not in scope.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid's standing approval (2026-10-20) to push, open PRs into `develop` and decide; the coordinator asked for these fixes without weaker checks.
Decided: a missing performance folder fails with HE-PERFORMANCE-SUITE, not a pass. An empty jscpd report passes only when a `--min-tokens 1` scan finds the files. OSV skips a uv.lock with no registry, Git or URL package. Setup adds pytest `pythonpath` only for a project uv does not install and that has no pytest settings. Code outside `sources` fails the check instead of a silent gap. An import root needs a submodule. Without a shipping policy, size checks also try `origin/HEAD` and Git's default branch name.

## Acceptance + steps

- [x] A missing performance folder names the rule → `tests/test_greenfield.py::test_missing_performance_suite_names_the_requirement`.
- [x] An empty jscpd report passes only when a rescan finds files → `tests/test_greenfield.py::test_jscpd_passes_files_below_its_minimum_only_when_a_rescan_finds_them`.
- [x] Tests import root modules of a project uv does not install → `tests/test_greenfield.py::test_tests_import_root_modules_of_a_project_uv_does_not_install`.
- [x] Code added after setup must join the sources → `tests/test_greenfield.py::test_python_code_added_after_setup_must_join_the_checked_sources`.
- [x] The import contract waits for a submodule → `tests/test_greenfield.py::test_import_contract_waits_for_a_package_with_submodules`.
- [x] OSV needs no scan when uv.lock locks no third-party package → `tests/test_greenfield.py::test_osv_needs_no_scan_when_uv_locks_no_third_party_package`.
- [x] A small change without a remote stays small → `tests/test_greenfield.py::test_small_change_without_a_remote_compares_with_the_local_default_branch`.

## Baseline + execution

Result: Passed
Evidence: `develop` 3620a68 in the cloud: a fresh `uv init --app` project with Hard Eng failed performance (exit 4), duplicates, vulnerabilities (exit 128) and tests (import error); a no-remote branch was sized big. Each new test failed before its fix.
Execution: One builder, one commit per fault.

## Risks + recovery

A project that left code out of `sources` on purpose now fails the check until it lists that code. Revert the commit of one fault to undo it.

## ux_reference

N/A — command-line checks with no visual surface.

## Verification

Result: Passed
Evidence: Fresh `uv init --app` project with this branch installed: an agent-like change (calc.py, unit tests, a performance test, pytest as a dev dependency, calc.py added to sources) passes every gate. Branch full suite: 1,855 passed; the same 6 environment failures as `develop` (no Dart or Swift in this container). Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the fresh-project run above uses the real installer and the real tools.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
