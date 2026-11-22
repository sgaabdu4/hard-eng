# Bump building-flutter-apps submodule to 64fd41a

Status: Complete

## Outcome + scope

Bump `.agents/skill-sources/building-flutter-apps` from `2545f35` to `64fd41a` so `hard-eng` carries the merged upstream `building-flutter-apps` documentation updates:
- PR #43 (`be933df`): `AsyncValue` reload pattern that preserves prior data during refresh (with family-key guidance for scoped providers) and `core/widgets` atom/molecule examples across skill references.
- PR #47 (`64fd41a`): `dart migrate` default one-minor step, `.0` patch requirement, bundled Flutter Dart SDK check, and `PlatformDispatcher.instance.onError` synchronous return with `Future<void>.sync` error containment in Crashlytics handlers.

Non-goals: changing analyzer plugin pins (`flutter_skill_lints` stays `^0.15.0` and `riverpod_lint` stays `^3.1.9`), modifying `.hooks/` logic, or releasing `develop` to `main`.

## Sources + coverage

Sources: N/A — user request is the only source.
Deliverables: None

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps`, `tests/test_submodules.py`, `tests/test_dart_config.py`, `tests/test_dart_nested_plugins.py`, `tests/test_ui_rules.py`.
Same cause: N/A — routine submodule pointer update following merged upstream PRs #43 and #47 in `sgaabdu4/building-flutter-apps`.
Single source: `.agents/skills/building-flutter-apps` symlinks directly to `.agents/skill-sources/building-flutter-apps/skills/building-flutter-apps`. No files inside `.agents/skill-sources/building-flutter-apps/skills/building-flutter-apps/references/analysis_options.yaml` changed between `2545f35` and `64fd41a`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User authorized fixing the upstream `building-flutter-apps` documentation and updating `hard-eng` with the delivered changes.

## Acceptance + steps

- [x] Submodule `.agents/skill-sources/building-flutter-apps` points to `64fd41a4d7b8388b9d30e171d01d7d334b2b3ca4` with canonical analyzer plugin pins unchanged and Dart config and nested plugin validation passing → `tests/test_dart_config.py::test_dart_setup_preserves_generated_excludes_and_native_yaml_list` + `tests/test_dart_config.py::test_a_flutter_package_without_flutter_skill_lints_is_refused` + `tests/test_dart_nested_plugins.py::test_dart_setup_migrates_nested_plugin_overrides` pass.

## Baseline + execution

Result: Passed
Evidence: Checked out `64fd41a4d7b8388b9d30e171d01d7d334b2b3ca4` in `.agents/skill-sources/building-flutter-apps` from `origin/develop` (`3c909a55`); `git -C .agents/skill-sources/building-flutter-apps diff --stat 2545f35..64fd41a` confirmed 11 Markdown reference files changed (`30 insertions, 21 deletions`) and zero changes to `analysis_options.yaml`.
Execution: Single-agent update in an isolated worktree off `origin/develop` (`3c909a55`).

## Risks + recovery

Risk: Minimal; only reference prose and Dart/Flutter snippet examples changed, and both upstream PRs passed `building-flutter-apps` CI and independent review before delivery. Recovery: revert the merged PR commit on `develop` (or revert every commit of this PR in reverse order if rebased) to restore `2545f35`.

## ux_reference

N/A — submodule pointer update for Markdown documentation only; no visual or UI surface changes.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_dart_config.py tests/test_dart_nested_plugins.py tests/test_ui_rules.py tests/test_submodules.py -q` passed (`154 passed in 36.35s`) with all submodules initialized and `.agents/skill-sources/building-flutter-apps` at `64fd41a4d7b8388b9d30e171d01d7d334b2b3ca4`.
E2E: N/A — submodule pointer update for documentation references only; no interactive end-to-end user journey changed.
Real service: N/A — no external runtime service or API call changed.
Retro: What worked: keeping `building-flutter-apps` documentation fixes in upstream PRs first and bumping the submodule cleanly afterwards avoided downstream drift. Prevention: none needed; existing submodule and Dart config suites enforce pin and profile consistency.

Review declined: `freezed-sealed.md:139` showing retained value on refresh error without an error notice, and `core-stack.md:44`/`core-stack.md:55` fresh-checkout `flutter pub get` before `--dry-run` and preserving `--target-sdk` with `--step=all` :: both files live in the upstream `sgaabdu4/building-flutter-apps` repository, already passed upstream CI and independent review in PR #43 and PR #47, and cannot be edited directly in `hard-eng`; any further prose refinement belongs in a separate `building-flutter-apps` PR.

Delivery target: Merge
Delivery: Pending — required remote proof.
