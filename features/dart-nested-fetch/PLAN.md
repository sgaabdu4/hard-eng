# Dart nested package fetch

Status: Complete

## Outcome + scope

When pre-push or a narrowed check selects a Dart package, its lockfile gate runs for every Dart package nested inside it. A Dart analyzer of the outer package reads the nested ones, so without their packages fetched it reports every import there as missing. Non-goals: other languages, other gate roles and full checks, which already run every lockfile gate.

## Repository context

Owners: `selected_services` in `.hooks/gate_config.py` keeps lockfile and vulnerability gates of packages that hold a selected package. It did not keep them for packages held inside a selected Dart package. `.hooks/project_setup.py` forbids Dart strict analysis from excluding project files, so a project cannot work around it. Found in the 2026-10-20 timing run on installed projects: one project's pre-push failed with thousands of unresolved imports after a root-only change.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 to fix the failing checks from the timing run. Decided: keep only the lockfile gate of the nested Dart package, since its tests and other gates are not needed to analyze the outer one.

## Acceptance + steps

- [x] A change in a root Dart package keeps the nested Dart package's lockfile gate only, and leaves a nested JavaScript package out → `tests/test_affected_selection.py::test_root_dart_analysis_fetches_nested_dart_packages_under_pre_push`.
- [x] Pre-push still leaves dependents to CI → `tests/test_affected_selection.py::test_pre_push_scope_checks_changed_packages_without_dependents`.

## Baseline + execution

Result: Passed
Evidence: `develop` 2bf22ce: the new test failed; the nested package was missing from the selection.
Execution: One builder; failing test first, then the nested case in `selected_services`.

## Risks + recovery

Pre-push in a Dart repository with nested packages now also fetches their packages, which adds their `pub get` time. Revert the `elif` branch in `selected_services` to restore the old selection.

## ux_reference

N/A — gate selection with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1,860 passed; the same 6 environment failures as `develop` (no Dart or Swift in this container). Ruff format and lint pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the test runs the real selection against a real Git repository.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
