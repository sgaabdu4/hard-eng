# Trello coordinator runs from the main checkout

Status: Complete

## Outcome + scope

A coordinator thread started in a T3 worktree kept reading the skill from its own branch, so Hard Eng updates on the main branch never reached it. The run steps now stop a coordinator that runs in a worktree and tell the owner to start it from the main checkout; the T3 host notes say to start it there. Non-goals: moving a running thread, updating a worktree branch.

## Repository context

Owners: `.agents/skills/trello-coordinator/references/run.md` (run order), `references/hosts.md` (T3 start).
Same cause: N/A — the state folder and secrets already resolve to the main checkout; only the skill text came from the worktree branch.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-06 answered "yes pls" to adding this rule, with merge after green checks for the coordinator work.

## Acceptance + steps

- [x] The first run step stops a coordinator in a worktree and names the main checkout → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after PR 501 merged; the new assertion failed before the fix.
Execution: one session; failing test first.

## Risks + recovery

A coordinator already running in a worktree stops on its next run and says why. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0; 25 coordinator tests passed.
E2E: N/A — no user journey; a real project's coordinator now runs from the main checkout and set its own schedule.
Delivery target: PR
Delivery: Pending — PR into develop.
