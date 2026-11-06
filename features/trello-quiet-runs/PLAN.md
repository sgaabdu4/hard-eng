# Trello coordinator runs stay quiet and on schedule

Status: Complete

## Outcome + scope

A day of real coordinator runs showed four gaps. Quiet runs sent several lines that repeated standing waits and not-checked items, and a still-working worker produced status messages. The schedule interval changed outside the coordinator, and the run only checked that a schedule existed. `update-pr` failed while the session's own background update held the lock, which cost two runs. The T3 start line did not name the coordinator role's model. Now a quiet run sends one line, the schedule is reset to `timing.everyMinutes`, `update-pr` waits for a running update and the start line names the model. Non-goals: run statistics, a decider field, changing a running coordinator thread.

## Repository context

Owners: `.agents/skills/trello-coordinator/references/run.md` (report), `references/hosts.md` (T3 start + schedule), `.hooks/update_pr.py` (publish).
Same cause: `update_runner.locked_update` refuses a second update by design; only `update-pr` should wait, because it publishes the branch that run prepares.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-06: "do a full analysis and then see what makes it better and then let's do it"; merge after green checks for the coordinator work.
Decision: `trello.json` `timing.everyMinutes` is the one place for the interval; a different live interval is reset and the owner is told once.
Decision: `update-pr` waits on the shared update lock without a time limit; the background update has its own limits.

## Acceptance + steps

- [x] The report rules say a quiet run is one line and a still-working worker sends no message; the T3 start names the coordinator role's model; a schedule whose `everyMs` differs is reset by its `scheduledTaskId` → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] `update-pr` started while another update holds the lock waits, then opens one pull request → `tests/test_update_pr.py::test_update_pr_waits_for_the_background_update_instead_of_failing`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after PR 506 merged; both new tests failed before the fix.
Execution: one session; failing tests first.

## Risks + recovery

A stuck background update makes `update-pr` wait until the caller's time limit. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: focused update and coordinator suites passed; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey; the updater test runs real git and a real file lock.
Delivery target: PR
Delivery: Pending — PR into develop.
