# Let a new empty repository receive its first push

Status: Ready

## Outcome + scope

Pre-push accepts the first push to a remote with no branches, after a full `check` with no `--base`; a failing gate still refuses it. Once the remote has branches, direct base pushes stay blocked, and a base missing from a populated remote still fails. Fixes issue #178. Non-goals: other push rules.

## Repository context

Owners: `.hooks/ship_actions.py` `pre_push` refused every base push and `remote_base` raised when the remote had no base; `.hooks/update.py` passes `remote_base` to the candidate check.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix the open hard-eng issues.

## Acceptance + steps

- [x] First push of `main` to an empty remote runs the full check: it passes when the gate passes and is refused when it fails; a later direct base push is blocked → `test_first_push_to_an_empty_remote_checks_everything`.
- [x] A missing base on a populated remote still fails → `test_initial_push_uses_current_remote_base_and_exact_revision`.

## Baseline + execution

Result: Passed
Evidence: Main `a7693e7`. The new test failed on that code: the base push was refused as a direct base update.
Execution: One commit.

## Risks + recovery

A first push to an empty remote is not diffed against any base, so the check covers the whole project. Recovery: revert the commit.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — a real pre-push against an empty bare remote.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
