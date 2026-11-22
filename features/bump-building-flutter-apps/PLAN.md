# Bump building-flutter-apps submodule to 2545f35

Status: Complete

## Outcome + scope

Bump `.agents/skill-sources/building-flutter-apps` from `a66aed1` to `2545f35` so `hard-eng` carries the `dart migrate` guidance and `flutter_skill_lints: ^0.15.0` canonical profile, and update the canonical plugin pin expectations in `tests/test_dart_config.py`. Non-goals: changing Dart boundary logic or releasing `develop` to `main`.

## Sources + coverage

Sources: N/A — user request is the only source.
Deliverables: None

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps`, `tests/test_dart_config.py`, `.hooks/dart_boundaries.py`, `.hooks/project_setup.py`.
Same cause: N/A — routine submodule pin update following merged changes in `building-flutter-apps` (`555fb909` and `2545f35e`).
Single source: Canonical Flutter analyzer plugin version is owned by `.agents/skill-sources/building-flutter-apps/skills/building-flutter-apps/references/analysis_options.yaml` (symlinked at `.agents/skills/building-flutter-apps/references/analysis_options.yaml`). Searched `tests/` and `.hooks/` for `0.14.0` and `0.13.4`; updated all four `flutter_skill_lints` test assertions in `tests/test_dart_config.py` to `^0.15.0` (the remaining `0.14.0` hits in `tests/test_gate_tools.py` and `tests/test_governing_ruff.py` are Ruff versions, unrelated).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Full-access autonomous execution; user explicitly approved bumping `.agents/skill-sources/building-flutter-apps` in this thread.

## Acceptance + steps

- [x] Submodule `.agents/skill-sources/building-flutter-apps` points to `2545f35e067414728ae7e2aba8be1a0aebab346c` and canonical plugin validation accepts `flutter_skill_lints: ^0.15.0` while migrating `^0.14.0` → `tests/test_dart_config.py::test_dart_setup_preserves_generated_excludes_and_native_yaml_list` + `tests/test_dart_config.py::test_dart_setup_migrates_known_plugin_with_rules` + `tests/test_dart_config.py::test_a_flutter_package_without_flutter_skill_lints_is_refused` + `tests/test_dart_config.py::test_dart_setup_migrates_locally_included_plugin_profile` pass.

## Baseline + execution

Result: Passed
Evidence: Before editing `tests/test_dart_config.py`, `uv run pytest tests/test_dart_config.py tests/test_ui_rules.py -q` failed on the four `^0.14.0` assertions (expecting `^0.15.0`) and one missing `appwrite-backend` submodule init in the fresh worktree.
Execution: Single-agent update in isolated worktree `wt/bump-bfa` off `origin/develop` (`f7f48275`).

## Risks + recovery

Risk: When `develop` is next released to `main`, installed Flutter projects still pinned to `flutter_skill_lints: ^0.14.0` will be prompted to migrate to `^0.15.0`. Recovery: revert this single commit on `develop` to restore `a66aed1` and `^0.14.0`.

## ux_reference

N/A — submodule pointer and Dart unit test update only; no visual or UI surface changes.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_dart_config.py tests/test_ui_rules.py -q` passed (`144 passed in 13.94s`) with all submodules initialized and `.agents/skill-sources/building-flutter-apps` at `2545f35e067414728ae7e2aba8be1a0aebab346c`. Full CI + Canary will verify on the PR to `develop`.
E2E: N/A — submodule pin and Python unit-test update only; no interactive end-to-end user journey changed.
Real service: N/A — no external runtime service or API call changed.
Retro: What worked: checking `tests/test_dart_config.py` immediately caught the `^0.14.0 -> ^0.15.0` canonical plugin shift before pushing. Prevention: none needed; the existing test suite already enforces alignment with the canonical `analysis_options.yaml`.

Delivery target: Merge
Delivery: Pending — required remote proof.
