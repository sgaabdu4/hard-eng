# Migrate older analyzer plugin pins in nested Dart analysis profiles

Status: Complete

## Outcome + scope

Make `configure_dart` in `setup.py` migrate outdated analyzer plugin pins in nested `analysis_options.yaml` files under a Dart package's sources, `test/`, and `tests/` folders (and their local includes), using the same nested-file discovery helper as `validate_dart_typing`. Non-goals: changing Dart validation strictness or modifying plugin version rules.

## Sources + coverage

Sources: N/A — user request following PR #685 review finding is the only source.
Deliverables: None

## Repository context

Owners: `.hooks/dart_boundaries.py`, `setup.py`, `tests/test_dart_config.py`.
Same cause: Earlier fix (`test_dart_setup_migrates_locally_included_plugin_profile`) added `migrate_included_dart_plugins` for files `include:`d by the root `analysis_options.yaml`; it helped upward/shared includes and had no effect on nested `analysis_options.yaml` files under `lib/`, `test/`, or `tests/` that include the root file while overriding `plugins:`. Searched `.hooks/` and `setup.py` for `migrate_included_dart_plugins` and `validate_dart_typing`; `configure_dart` in `setup.py` is the only migration caller.
Single source: Nested `analysis_options.yaml` discovery is owned by `nested_dart_options` in `.hooks/dart_boundaries.py` (used by both `validate_dart_typing` and `migrate_nested_dart_plugins`). Per-file plugin migration is owned by `_migrate_dart_plugin_file` in `.hooks/dart_boundaries.py` (used by both `migrate_included_dart_plugins` and `migrate_nested_dart_plugins`). Searched `.hooks/` and `setup.py` for `rglob("analysis_options.yaml")`; merged the previous inline loop in `validate_dart_typing` into `nested_dart_options`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User requested fixing the nested analyzer profile migration finding surfaced during PR #685 review.

## Acceptance + steps

- [x] `configure_dart` migrates older `flutter_skill_lints` pins inside nested `analysis_options.yaml` files under package `sources` and `test/` (and their local `include:` targets) so `validate_typing` passes afterward → `tests/test_dart_config.py::test_dart_setup_migrates_nested_plugin_overrides` passes (failed before the fix with `AssertionError: assert '^0.14.0' == '^0.15.0'`).

## Baseline + execution

Result: Passed
Evidence: Repro test `tests/test_dart_config.py::test_dart_setup_migrates_nested_plugin_overrides` failed on `origin/develop` (`00dfff6f`) with `AssertionError: assert '^0.14.0' == '^0.15.0'`. After adding `nested_dart_options` and `migrate_nested_dart_plugins`, `uv run pytest tests/test_dart_config.py -q` passed (`56 passed in 4.12s`).
Execution: Single-agent fix in isolated worktree `wt/fix-nested-dart-plugins` off `origin/develop` (`00dfff6f`).

## Risks + recovery

Risk: Symlinks under `sources` or `test/` could point outside the repository root; `_migrate_dart_plugin_file` checks `resolved.is_relative_to(root.resolve())` before reading or queuing edits, and `migrate_nested_dart_plugins` skips child package folders in `children`. Recovery: revert the merged PR commit on `develop` (or revert this PR's commits in reverse order).

## ux_reference

N/A — Python setup and Dart analysis configuration migration only; no visual or UI surface changes.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_dart_config.py -q` passed (`56 passed in 4.12s`, including `test_dart_setup_migrates_nested_plugin_overrides`, which failed before the fix). Full CI + Canary will run on the PR to `develop`.
E2E: N/A — setup/config migration unit behavior only; no interactive end-to-end user journey changed.
Real service: N/A — no external runtime service or API call changed.
Retro: Escaped-bug repro `tests/test_dart_config.py::test_dart_setup_migrates_nested_plugin_overrides` failed before the fix and passed after; sharing `nested_dart_options` prevents discovery drift between `validate_dart_typing` and `configure_dart`.

Delivery target: Merge
Delivery: Pending — required remote proof.
