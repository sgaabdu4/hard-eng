# Keep update branch work made during a build

Status: Complete

## Outcome + scope

A background update never replaces `hard-eng/update` when someone commits to it or checks it out while the update is being built. The update keeps that work and says to rerun once it is finished.
Non-goals: no change to when an update starts, what it builds, or how an unfinished branch is detected before the build.

## Repository context

Owners: [update_runner.py](../../.hooks/update_runner.py) `build_update` and `set_update_branch`; [update_pr.py](../../.hooks/update_pr.py) `branch_worktree`.
Evidence: `set_update_branch` read the branch tip at the end of the build and used it as the expected value, so the compare-and-swap could not catch a commit made during the build. The unfinished-work and checked-out guards ran only before the build. An independent review of a consumer update PR found it and a test reproduced it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user approved fixing Hard Eng's own faults found during the release canary and consumer updates; merge when green after the canary.
Decisions: Read the branch tip before the guards and use it for the final compare-and-swap; check again that no worktree holds the branch just before moving it. A refused move returns a message and keeps the branch, instead of raising.

## Acceptance + steps

- [x] A commit made on the update branch while an update is built stays on the branch, and its worktree stays clean → `test_background_update_keeps_a_fix_committed_while_it_ran`, red before (the branch moved to the new update).
- [x] Existing update branch behaviour keeps passing → `tests/test_update_pr.py`, `tests/test_update_runner.py`.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, focused tests, full check, challenge, Codex loop, PR, CI, release canary, merge.

## Risks + recovery

A branch checked out but unchanged during the build is now kept; the next update moves it once it is free, as before the build. Recovery is reverting this branch.

## ux_reference

N/A — background updater; no product appearance.

## Verification

Result: Passed
Evidence: The new test failed before the fix and passed after; 60 updater tests passed.
E2E: N/A — the race needs two processes at one moment; the repository-level test drives the real updater and git.

Delivery target: Merge
Delivery: Pending — PR CI, release canary on the PR head, merge.
