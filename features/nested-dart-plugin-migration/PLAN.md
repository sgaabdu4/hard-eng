# Migrate older analyzer plugin pins in nested Dart analysis profiles

Status: Complete

## Outcome + scope

Make `configure_dart` in `setup.py` migrate outdated analyzer plugin pins in nested `analysis_options.yaml` files under a Dart package's sources, `test/`, and `tests/` folders (and their local includes), using the same nested-file discovery helper as `validate_dart_typing`. Non-goals: changing Dart validation strictness or modifying plugin version rules.

## Sources + coverage

Sources: N/A — user request following PR #685 review finding is the only source.
Deliverables: None

## Repository context

Owners: `.hooks/dart_boundaries.py`, `setup.py`, `tests/test_dart_nested_plugins.py`.
Same cause: Earlier fix (`test_dart_setup_migrates_locally_included_plugin_profile`) added `migrate_included_dart_plugins` for files `include:`d by the root `analysis_options.yaml`; it helped upward/shared includes and had no effect on nested `analysis_options.yaml` files under `lib/`, `test/`, or `tests/` that include the root file while overriding `plugins:`. Searched `.hooks/` and `setup.py` for `migrate_included_dart_plugins` and `validate_dart_typing`; `configure_dart` in `setup.py` is the only migration caller.
Single source: Nested `analysis_options.yaml` discovery is owned by `nested_dart_options` in `.hooks/dart_boundaries.py` (used by both `validate_dart_typing` and `migrate_nested_dart_plugins`). Per-file plugin migration is owned by `_migrate_dart_plugin_file` in `.hooks/dart_boundaries.py` (used by both `migrate_included_dart_plugins` and `migrate_nested_dart_plugins`). Searched `.hooks/` and `setup.py` for `rglob("analysis_options.yaml")`; merged the previous inline loop in `validate_dart_typing` into `nested_dart_options`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User requested fixing the nested analyzer profile migration finding surfaced during PR #685 review.

## Acceptance + steps

- [x] `configure_dart` migrates older `flutter_skill_lints` pins inside nested `analysis_options.yaml` files under package `sources` and `test/` (and their local `include:` targets) so `validate_typing` passes afterward → `tests/test_dart_nested_plugins.py::test_dart_setup_migrates_nested_plugin_overrides` passes (failed before the fix with `AssertionError: assert '^0.14.0' == '^0.15.0'`).
- [x] Nested migration skips initialized Git submodules, malformed/standalone test fixtures that do not include the package root `analysis_options.yaml`, and proven derived copies marked in `.gitattributes` → `tests/test_dart_nested_plugins.py::test_dart_setup_skips_submodules_malformed_fixtures_and_proven_copies` passes.

## Baseline + execution

Result: Passed
Evidence: Repro test `test_dart_setup_migrates_nested_plugin_overrides` failed on `origin/develop` (`00dfff6f`) with `AssertionError: assert '^0.14.0' == '^0.15.0'`. After adding `nested_dart_options` and `migrate_nested_dart_plugins` (with submodule, fixture, and proven-copy guards), `uv run pytest tests/test_dart_config.py tests/test_dart_nested_plugins.py -q` passed.
Execution: Single-agent fix in isolated worktree `wt/fix-nested-dart-plugins` off `origin/develop` (`00dfff6f`).

## Risks + recovery

Risk: Symlinks under `sources` or `test/` could point outside the repository root, or nested files could lie in submodules, test fixtures, or proven copies; `_migrate_dart_plugin_file`, `_inside_nested_repo`, `_includes_target`, and `proven_copies` exclude all four while migrating genuine nested package overrides. Recovery: revert the merged PR commit on `develop` (or revert this PR's commits in reverse order).

## ux_reference

N/A — Python setup and Dart analysis configuration migration only; no visual or UI surface changes.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_dart_config.py tests/test_dart_nested_plugins.py -q` passed (`57 passed`, including `test_dart_setup_migrates_nested_plugin_overrides` and `test_dart_setup_skips_submodules_malformed_fixtures_and_proven_copies`). Full CI + Canary will run on the PR to `develop`.
E2E: N/A — setup/config migration unit behavior only; no interactive end-to-end user journey changed.
Real service: N/A — no external runtime service or API call changed.
Retro: Escaped-bug repro `tests/test_dart_nested_plugins.py::test_dart_setup_migrates_nested_plugin_overrides` failed before the fix and passed after; sharing `nested_dart_options` prevents discovery drift between `validate_dart_typing` and `configure_dart`.

Review declined: when a source package and its proven derived copy both hold a stale nested `analysis_options.yaml`, `setup.py` migrates only the source package and leaves the derived copy unchanged :: intentional; `setup.py` never rewrites proven derived copies (the same rule already applies when `setup.py` migrates a source package's root `analysis_options.yaml`), because syncing derived copies belongs to the project's own copy script on the update PR.

Delivery target: Merge
Delivery: Pending — required remote proof.
