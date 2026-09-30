# Show the outside-lib Dart test guidance only when coverage misses a file

Status: Complete

## Outcome + scope

The guidance for testing Dart outside `lib/` appears only when the coverage report omits a measurable file there. Packages whose non-lib sources are export barrels, declaration-only files or test harnesses no longer print it on every gate run. Installed gate files carrying the old command are rewritten on update.

Non-goals: which sources a package declares, and how coverage classifies files.

## Repository context

Owners:
- `.hooks/project_setup.py` `run_vm_tests`: printed the guidance whenever no test imported a non-lib source, even when that source had nothing to cover.
- `.hooks/project_setup.py` `outside_lib_coverage`: matched only the plain generated command, so an installed command kept its old VM step.
- `.hooks/reports.py` `line_coverage`: already fails naming the uncovered production files after excluding barrels and declaration-only files.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix every open Hard Eng finding; this one was reported by the consumer rollout.

## Acceptance + steps

- [x] No guidance without a finding; guidance with the coverage failure → `test_flutter_dart_outside_lib_is_measured_on_the_dart_vm`.
- [x] An export-only non-lib file passes → the same test.
- [x] An installed command with the old step is regenerated, and dropped when only `lib/` remains → `test_update_regenerates_an_installed_dart_vm_coverage_command`.

## Baseline + execution

Result: Passed
Evidence: both tests fail against main `efc06571`; applying `outside_lib_coverage` to two installed Flutter gate files removes the old guidance from their tests command.
Execution: One builder on branch `fix/outside-lib-message`.

## Risks + recovery

A hand-edited tests command is left unchanged because it matches no generated form. Recovery is reverting the commit.

## ux_reference

N/A — gate output only; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` passed all 18 gates in 122s (1162 tests, 89.93% line coverage).
E2E: N/A — gate command generation; installed repositories take the change with their next update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
