# Keep analyzer plugin findings visible

Status: Complete

## Outcome + scope

Pin building-flutter-apps v5.11.1 so installed Flutter projects get skill guidance and a pre-flight audit that run `dart analyze --fatal-infos` from the package root. `flutter analyze` and `dart analyze <dir>` skip analyzer plugin diagnostics while printing "No issues found!". Non-goals: changing Hard Eng's `types-lint` gate, which already runs package-root `dart analyze --fatal-infos .`.

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps` submodule. Upstream: [building-flutter-apps v5.11.1](https://github.com/sgaabdu4/building-flutter-apps/releases/tag/v5.11.1). No plugin pin change, so `tests/test_dart_config.py` is unchanged.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User approved releasing the skill fix, bumping Hard Eng's pin, and merging once CI passes.

## Acceptance + steps

- [x] Submodule points at v5.11.1 (`cd17397`) → `git submodule status` shows it.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `c225189` + this plan → exit 0; 17/17 gates PASS.
Execution: One builder; submodule bump.

## Risks + recovery

Projects whose pre-flight audit previously passed with info diagnostics now fail it, which is intended; they fix the diagnostics.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `git submodule status` → `cd17397` (v5.11.1). `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS.
E2E: N/A — skill content pin; proof is the submodule revision and gate.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
