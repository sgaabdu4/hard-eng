# Analyze root Dart packages from the package root so analyzer plugins run

Status: Complete

## Outcome + scope

Fix [#183](https://github.com/sgaabdu4/hard-eng/issues/183): setup and update give a root Dart package the template's package-root `dart analyze --fatal-infos .` types gate instead of expanding it to `lib test …`, and upgrade Hard Eng's own earlier expanded gate in place, because `dart analyze` skips analyzer plugins when given explicit paths. Non-goals: nested package scopes, analyzer flags, project-owned analyzer commands.

## Repository context

Owners: `setup.py` `configure_typing_checks` + `adopt_root_dart_gates` (since #110 they expanded `.` to declared sources and existing test roots); tests in `tests/test_setup.py`.
Evidence (Dart 3.13.4, riverpod_lint 3.1.9 via `plugins:`, a Notifier with a public field): `dart analyze --fatal-infos lib` → "No issues found!"; `dart analyze --fatal-infos` and `... .` → `avoid_public_notifier_properties`. Package-root analysis skips dot directories, so installed `.agents/` skill templates stay out of scope: a planted error there was not reported, one in `tool/` was.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all open Hard Eng issues in one PR with proper testing and an adversarial review.

## Acceptance + steps

- [x] Fresh root Dart install → exactly one analyzer gate, `dart analyze --fatal-infos .` → `test_plain_dart_uses_native_coverage_tool`.
- [x] Hard Eng's `types-lint` or `strict-types-lint` at `dart analyze --fatal-infos lib test` → the same gate becomes `... .`, stable on repeat → `test_root_dart_directory_analyzer_returns_to_package_root`; earlier duplicate states collapse to one package-root gate → `test_root_dart_update_consolidates_duplicate_analyzers`.
- [x] A project package-root analyzer (`dart analyze --fatal-infos`, with or without `.`) stays the sole types owner; a narrower or weaker project analyzer, including `lib test`, becomes `project-types` beside strict `.` → `test_root_dart_analyzer_is_reused_only_when_it_covers_the_package`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `2aea113` (after `git submodule update --init --recursive` reset this worktree's skill submodule to the recorded commit) → exit 0; all gates PASS, 932 tests, 90.49% line coverage.
Execution: One builder at the existing owner.

## Risks + recovery

Package-root analysis also covers `bin/`, `tool/` and nested packages, so a consumer may see new real findings there. A project-owned explicit-directory analyzer now counts as narrower and gains the strict `.` gate beside it. A plugin whose `analyzer` requirement conflicts with the project's resolved `analyzer` (for example through `package:test`) reports nothing at any scope; that is the consumer's dependency resolution, not the gate's scope. Recovery: revert the commit.

## ux_reference

N/A — setup behavior with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_setup.py tests/test_package_discovery.py` → 78 passed; Ruff, Pyrefly, Vulture and complexity checks clean. Full gate: see the combined result in [dart-web-test-support](../dart-web-test-support/PLAN.md#verification).
E2E: Passed — synthetic Flutter package with the riverpod_lint plugin and a public Notifier field, installed from this revision: its types gate set to the earlier `dart analyze --fatal-infos lib test` → `PASS types-lint` with "No issues found!"; rerunning `setup.py` rewrote it to `dart analyze --fatal-infos .`, and Hard Eng's `run_gate` then reported `avoid_public_notifier_properties` and `FAIL types-lint`.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
