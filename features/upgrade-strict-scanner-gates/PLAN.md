# Give older scanner gates their required strict flags on update

Status: Complete

## Outcome + scope

Setup appends the strict flag the check already requires to an older scanner gate: `--no-respect-inline-disables` for React Doctor, `--strict` for `dart-decimate check`, `--fail-on-issues` for a fallow scan and `--gate all` for a fallow audit with no `--gate`. It runs for every package on install and on update. A gate that reaches its scanner through a package script or a command chain, and a fallow audit with an explicit `--gate`, are left for the check's own message. No new file other than this plan.

## Repository context

Owners: `.hooks/project_setup.py` and `setup.py` `plan_install`, which already adapts each package's gates on every install and update. PR 118 made these flags mandatory in `.hooks/fallow_report.py` `scanner_failure` and chose to leave installed gate commands alone. A trial of main at 25a544c on real projects showed the effect: one project's check failed in under a second on every change after updating, and another project already on a revision with the validation had three React Doctor gates without the flag, so its check could not run at all.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked that generated gates be fixed for other projects and that an older gate be upgraded to the new form on update; this reverses PR 118's stated assumption that installs keep their commands. Only flags whose absence the check reports with an exact `add --flag` message are appended. The flags can surface findings that an inline suppression hid; those must be repaired, which is the existing rule. Merge awaits the user's go-ahead.

## Acceptance + steps

- [x] Each older command fails the real validator before and passes it after; a second run changes nothing; a script gate and an explicit `--gate new` audit are untouched → `test_update_gives_an_older_scanner_gate_its_required_strict_flags`.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 25a544c, whose push CI run 35619284381 passed.
Execution: Single session on `feature/upgrade-strict-scanner-gates`.

## Risks + recovery

A project with findings hidden behind inline suppressions sees them after its next update and must repair them before its check passes. Recovery is reverting this branch; an upgraded project keeps valid commands either way.

## ux_reference

N/A — generated gate commands only; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a throwaway worktree of a real four-package JavaScript project installed at b50c3c8, the check first stopped at `React Doctor must not honour inline suppressions`. After the real `setup.py` from this branch ran with that project's previous source, all three React Doctor gates carried the flag and the check went on to select and run gates. In a second real project the flag, added by hand, surfaced no hidden findings and all 18 gates passed in 33 seconds.
Evidence: The new test passes for five older commands. The full check result is recorded in the delivery line below.

Delivery target: PR
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks, 793 tests and 4 performance checks passed. A first run failed the types gate on an untyped list and report in the new code; both were annotated before the passing run. PR CI and merge remain unverified.
