# Trello coordinator sets its schedule on the first run

Status: Complete

## Outcome + scope

A first manual T3 Code run did one board check and stopped: it read only the run and command steps, never the host notes, so it made no schedule. The run order now sends the coordinator to the host's schedule check right after `probe`. Non-goals: a script command for scheduling, changes to the host notes.

## Repository context

Owners: `.agents/skills/trello-coordinator/references/run.md` (run order).
Same cause: the schedule rule lives only in `references/hosts.md`, which the run order never named; no other run step depends on that file.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-05: "We need to automate as much as possible", with merge after green checks for the coordinator work.

## Acceptance + steps

- [x] The first run step names the schedule check and links the host notes → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after PR 497 merged; the new assertion failed before the fix.
Execution: one session; failing test first.

## Risks + recovery

One extra host call per run. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0; 68 coordinator and board tests passed.
E2E: N/A — a real schedule needs the T3 host; a live coordinator thread made its schedule after following the same host rule.
Delivery target: PR
Delivery: Pending — PR into develop.
