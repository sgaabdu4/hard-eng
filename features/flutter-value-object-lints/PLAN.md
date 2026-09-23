# Adopt Flutter value-object lints

Status: Complete

## Outcome + scope

Pin building-flutter-apps v5.11.0 so installed Flutter projects get `flutter_skill_lints ^0.12.0` (value-object lints) on their next update. Non-goals: fixing consumer apps' raw domain fields; changing the updater.

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps` submodule; `migrate_dart_plugins` in `.hooks/project_setup.py` reads the canonical `references/analysis_options.yaml`; `tests/test_dart_config.py` encodes the canonical pin. Upstream: [flutter_skill_lints v0.12.0](https://github.com/sgaabdu4/flutter_skill_lints/releases/tag/v0.12.0), [building-flutter-apps v5.11.0](https://github.com/sgaabdu4/building-flutter-apps/releases/tag/v5.11.0).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User approved bumping the pin, opening a Hard Eng PR, and merging it once CI passes.

## Acceptance + steps

- [x] Submodule points at v5.11.0 (`7f3f1cd`) → `git submodule status` shows it.
- [x] Older ordinary pins (`0.11.2`, `^0.11.2`) now migrate to `^0.12.0`; `0.12.0` and ranges stay → `tests/test_dart_config.py` passes.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `faec5fa` + this plan → exit 0; 17/17 gates PASS.
Execution: One builder; submodule bump + test table.

## Risks + recovery

Installed Flutter projects with raw domain fields fail `types-lint` after updating, which is intended; they fix the fields or stay on the previous Hard Eng revision until they do.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `git submodule status` → `7f3f1cd` (v5.11.0). `uv run pytest -q tests/test_dart_config.py` → 54 passed, including `0.11.2`/`^0.11.2` → migrate and `0.12.0`/`^0.12.0` → keep. Full Complete gate below.
E2E: N/A — configuration pin; proof is the migration tests and gate.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
