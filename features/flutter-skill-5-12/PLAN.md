# Pin building-flutter-apps v5.12.0 and flutter_skill_lints ^0.13.0

Status: Complete

## Outcome + scope

Pin building-flutter-apps v5.12.0 so installed Flutter projects get skill examples that analyze clean under flutter_skill_lints 0.13.0 and a `flutter_skill_lints: ^0.13.0` plugin pin. The plugin migration then upgrades consumer pins older than 0.13.0. Non-goals: changing Hard Eng gates or the migration logic.

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps` submodule; `tests/test_dart_config.py` for the canonical plugin pin. Upstream: [building-flutter-apps v5.12.0](https://github.com/sgaabdu4/building-flutter-apps/releases/tag/v5.12.0) and [flutter_skill_lints 0.13.0](https://pub.dev/packages/flutter_skill_lints/versions/0.13.0).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User approved bumping Hard Eng's pin, releasing, and merging once CI passes.

## Acceptance + steps

- [x] Submodule points at v5.12.0 (`b9d069f`) → `git submodule status` shows it.
- [x] Canonical plugin pin is `^0.13.0`; 0.12.x pins migrate and 0.13.x pins stay → `python3 -m pytest tests/test_dart_config.py` passes.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Draft` on `6821a0b` + this change → exit 0; 17/17 gates PASS; 815 tests pass.
Execution: One builder; submodule bump plus migration test expectations.

## Risks + recovery

flutter_skill_lints 0.13.0 reports 43 new error codes, so consumer projects that update may fail `types-lint` until they fix the findings. That is intended, because each code enforces a skill MUST/NEVER rule. Recovery: revert this commit to restore v5.11.1 and `^0.12.0`.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `git submodule status` → `b9d069f` (v5.12.0). `python3 -m pytest tests/test_dart_config.py` → 56 passed. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS.
E2E: N/A — skill content pin; proof is the submodule revision, migration tests and gate.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
