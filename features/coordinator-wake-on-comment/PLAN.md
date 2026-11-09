# Coordinator wakes on a board comment and pauses when the board is quiet

Status: Complete

## Outcome + scope

On T3 Code, a stakeholder comment starts a coordinator run through a webhook task; the interval timer pauses after `timing.idleStopMinutes` quiet minutes, and a one-time alarm keeps chases, promises and due dates. The same change adds five coordinator rules from a review of a consumer coordinator's mistakes. Non-goals: wake on hosts other than T3 Code, Trello REST webhooks, changing the consumer's own coordinator rules.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (report fields), `board.py` (newest stakeholder comment from the fresh read), `commands.py` (`check` state), `config.py` (`timing`), `references/hosts.md` (schedule), `references/run.md`, `references/commands.md`, `SKILL.md`; tests in `tests/test_trello_report.py`, `tests/trello_fakes.py`, `tests/test_trello_coordinator.py`.
Evidence: T3 webhook tasks take `filters` and `dedupe.coalesceKey`; a fixed key renders to one hash, so a burst of comments becomes one run. Trello REST webhooks need a HEAD check that the T3 relay refuses, so the owner adds a Trello Automation rule that posts the commenter's username. A consumer board's workspace is on Trello's free plan (250 Automation runs a month); it had 12 stakeholder comments in its first 3 days.
Same cause: the old hosts rule reset the timer on every run, so any self-pause was undone; it is replaced, not patched. The five rules come from 18 quoted mistakes in a consumer coordinator thread on 2026-11-08 and 2026-11-09.
Single source: `idleStopMinutes` lives in `config.TIMING_HOURS`, and the docs test reads its row from there; the wake fields live in `report.WAKE_FIELDS`, which the docs test and the report tests read; promise and chase due times come from `promise_due` and `oldest_unanswered`, which both the lists and `nextDue` use. Searched `.agents/skills/` and `tests/` for `everyMinutes`, `promiseHours`, `chaseHours`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid approved the comment wake and quiet pause on 2026-11-09, relayed from another thread; in this thread he chose the alarm before a pause and asked for the five review rules in the same PR.
Decision: `idle` = quiet for `idleStopMinutes` and no `requests`, `owner`, `promises`, `silent` or `buried` item. Persistent lists (`testQueue`, `realCases`, `overdue`) do not keep the board awake; `realCases` adds a `chaseHours` alarm instead.
Decision: the token's own comments never count as heard, matching the wake filter; the owner's comments do not wake the coordinator.
Decision: `timer` pauses only after `wake` has run once, so a board whose Trello rule is not set up keeps its timer.

## Acceptance + steps

- [x] The board is idle only after the stop time, with nothing to answer → `tests/test_trello_report.py::test_the_board_goes_idle_only_after_the_stop_time` (59 minutes awake, 61 idle).
- [x] An unanswered request keeps a quiet board awake → `tests/test_trello_report.py::test_an_unanswered_request_keeps_a_quiet_board_awake`.
- [x] Our own comments never count as heard → `tests/test_trello_report.py::test_our_own_comments_never_count_as_heard`.
- [x] `nextDue` is the earliest future promise, chase or due date, and a real-case card adds `chaseHours` → `tests/test_trello_report.py::test_next_due_is_the_earliest_promise_chase_or_due_date`, `tests/test_trello_report.py::test_a_chase_or_a_real_case_check_sets_next_due`.
- [x] The reference lists every timing field and report field → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: `develop` c2fa3c57 passed its push runs (Hard Eng and Canary) on 2026-11-09.
Execution: this session, one builder; Reader passes by fresh subagents.

## Risks + recovery

- Trello's free plan allows 250 Automation runs a month per workspace; past it, comments stop waking the coordinator. Recovery: the hosts rule tells the owner when comments arrive and `wake` does not run.
- The webhook URL holds its token; anyone with it can start a run, and the run reads the board itself. Recovery: delete and recreate `wake`.

## ux_reference

N/A — no app screens; coordinator skill text and its script only.

## Verification

Result: Passed
Evidence: [TODO: focused tests, Reader passes, Complete check]
E2E: N/A — the script has no user journey; the fake board tests run the real `check` command.
Retro: [TODO]

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
