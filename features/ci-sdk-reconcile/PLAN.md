# Add missing SDKs to existing CI

Status: Complete

## Outcome + scope

When the updater meets an existing generated `.github/workflows/hard-eng.yml`, add SDKs that the project's packages now need (for example `flutter@latest` for a Flutter app added later) to the mise install and exec lines, dropping `dart@latest` once Flutter is present. Keep project-added tools. Non-goals: rewriting customised workflows, pinning Flutter versions, other CI changes.

## Repository context

Owners: `.hooks/ci_setup.py` (`configure_ci` existing-workflow branch only migrates pins, triggers and docs steps; `workflow_tools` computes SDKs only for new workflows); `tests/test_ci_setup.py`. Evidence: a Flutter app added after CI generation left CI installing only `dart@latest` while its gates call `flutter pub get` and `flutter test`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to build this, keep CI fast, and merge once CI passes.

## Acceptance + steps

- [x] Existing generated workflow with `dart@latest` and a new Flutter package → install and exec lines gain `flutter@latest`, lose `dart@latest`, keep `rust@latest` and pinned `pnpm@x` → new test passes; rerun makes no change.
- [x] Customised workflow without the generated lines and a missing SDK → left unchanged with a note naming the tool → new test passes.
- [x] Existing CI setup tests still pass → `uv run pytest -q tests/test_ci_setup.py`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `732b31c` + this plan → exit 0; 17/17 gates PASS.
Execution: One builder.

## Risks + recovery

CI speed: adding Flutter only happens when a package needs it, replaces the Dart download, and reuses the existing tool cache after one refresh. A tool list the regex misreads → leave the workflow untouched and print the note.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest -q tests/test_ci_setup.py` → 31 passed; both new tests fail with the reconcile call removed. Dry run of `configure_ci` on a real consumer's workflow + gate config: `dart@latest` → `flutter@latest` in install and exec, `pnpm@12.4.1` and `rust@latest` kept, no base tools added. Only package SDKs are added, so CI downloads nothing new unless a package needs it.
E2E: N/A — updater transformation; proof is the fixture tests and gate.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
