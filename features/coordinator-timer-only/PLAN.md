# Coordinator runs on its timer only

Status: Complete

## Outcome + scope

The trello-coordinator on T3 Code runs only on its interval `timer` at `timing.everyMinutes`. The comment webhook task `wake`, the quiet-board pause, the one-time `alarm` and the report fields `idle`, `quietMinutes` and `nextDue` are removed, with the `timing.idleStopMinutes` setting. A `trello.json` that still sets `idleStopMinutes` is refused with a line that says to delete it. Non-goals: Trello API webhooks, any other way to wake the coordinator, changes to the other report fields, the claim or the Claude Code and Codex schedules.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (`build`, `AWAKE`, `WAKE_FIELDS`, `due_times`, `last_heard`), `board.py` (`Snapshot.heard`), `commands.py` (`check`, `lastHeard` state), `config.py` (`TIMING_HOURS`, `GONE_TIMING`, `Config.idle_stop_minutes`); text in `references/hosts.md` (T3 Code schedule, pause check, claim stop, move steps), `references/run.md:11`, `references/commands.md` (timing row, three report rows); tests in `tests/test_trello_report.py`, `tests/test_trello_coordinator.py`.
Bug evidence: N/A — a removal on the maintainer's order, not a defect.
Same cause: N/A — no defect.
Single source: the wake code came in one commit (`ccaed336`). Searched the skill folder, `tests/`, `README.md` and `docs/` for `wake`, `idle`, `quietMinutes`, `nextDue`, `alarm`, `pause`, `lastHeard` and `idleStopMinutes`: only the owners above hold them. `first_check` stays, because the owner check also reads it. The helpers `promise_due`, `oldest_unanswered` and `card_due` stay, because `promises`, `silent` and `overdue` call them.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: the maintainer said "yes pls" on 2026-11-10 to removing the webhook from Hard Eng. Evidence they had: each comment uses one Trello Automation run, the free plan allows 250 a month for the workspace, and a real board's monthly comment count was several times that. When the quota runs out, a paused coordinator answers only every `chaseHours`. No board on the maintainer's machine has a `wake` task.
Decision: `idleStopMinutes` joins `GONE_TIMING`, so a `trello.json` that sets it gets "no longer used; delete idleStopMinutes", the same as `quietHours` and `timeZone`.
Decision: the schedule check still sets `timer` back to `enabled: true` at `everyMinutes`, so a timer that an older release slowed returns to full speed on its next run. It deletes only tasks titled `wake` or `alarm`, which only the older release made, because other tasks the owner made can be bound to the same thread; after deleting `wake` it tells the owner once to delete the Trello rule. Found by the Reader pass: without this, a leftover `wake` keeps using the Trello quota and keeps starting runs on a machine that lost the claim.
Decision: the claim stop deletes this host's `timer` only.

## Acceptance + steps

- [x] A `trello.json` with `timing.idleStopMinutes` is refused with "delete idleStopMinutes" → `tests/test_trello_coordinator.py::test_config_takes_timing_overrides_and_refuses_retired_fields` (fails on `develop`: the field is accepted).
- [x] The `check` report holds only the report lists and `runId`; every report test runs it through the fake's `report`, which asserts that each other field is a list → `tests/test_trello_report.py::test_a_ticked_due_date_is_not_overdue` (fails on `develop`: `idle` is not a list).
- [x] The reference rows and timing defaults match the code → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract` (fails on `develop`: the reference lists the three removed fields).
- [x] `hosts.md` names one T3 task, `timer`, with no pause check or Trello Automation steps, and deletes an old `wake` or `alarm`; `run.md` step 5 has no pause check → N/A — reference text; a Reader pass compares the old and new text.

Removed test: tests/test_trello_report.py :: test_the_board_goes_idle_only_after_the_stop_time :: it proved the `idle` and `quietMinutes` fields, which this change removes; the fake's `report` now fails on any field that is not a list.
Removed test: tests/test_trello_report.py :: test_an_unanswered_request_keeps_a_quiet_board_awake :: it proved the `idle` field, which this change removes.
Removed test: tests/test_trello_report.py :: test_our_own_comments_never_count_as_heard :: it proved `quietMinutes`, which this change removes.
Removed test: tests/test_trello_report.py :: test_next_due_is_the_earliest_promise_chase_or_due_date :: it proved `nextDue`, which this change removes.
Removed test: tests/test_trello_report.py :: test_next_due_is_the_promise_when_it_comes_first :: it proved `nextDue`, which this change removes.
Removed test: tests/test_trello_report.py :: test_next_due_is_a_chase_and_never_beyond_chase_hours :: it proved `nextDue`, which this change removes; `silent` chases keep their own test, `test_a_chase_restarts_the_silent_clock`.

## Baseline + execution

Result: Passed
Evidence: the branch starts from `develop` 1ada0528, whose `Hard Eng` push run and `Hard Eng`, `Canary`, `PR text` and `Release source` pull-request runs passed (`gh run list --commit`, 2026-11-10). On that code, with only the changed tests, 4 tests failed for the planned reasons: `idle` is not a list, `idleStopMinutes` is accepted, and the reference rows differ from `FIELDS`.
Execution: this session, alone: failing tests first, then the code and the reference text; a Reader subagent on Opus compares the changed reference text; the Complete check against `origin/develop`.

## Risks + recovery

- A consumer whose `trello.json` sets `idleStopMinutes` stops at `check` until the field is deleted. Recovery: the error names the field.
- A consumer that made a `wake` task and a Trello rule on the 2026-11-09 release keeps the rule until the owner deletes it; the rule's posts then reach no task. Recovery: the coordinator deletes `wake` and tells the owner once.
- Comments wait up to `everyMinutes` for an answer. Recovery: a lower `everyMinutes`.

## ux_reference

N/A — no app screens; coordinator script and reference text only.

## Verification

Result: Passed
Evidence: On 2026-11-10 the 4 changed tests failed first on the unchanged code, for the planned reasons. After the change, `tests/test_trello_report.py`, `tests/test_trello_coordinator.py` and `tests/test_trello_board.py`: 132 passed. A Reader subagent read the changed reference text against the code: no leftover reference to the removed feature and no meaning change beyond the removal, but no step handled a `wake` task left by the older release, which keeps using the Trello quota and keeps starting runs on a machine that lost the claim; the schedule check now deletes `wake` and `alarm` by title. `python3 .hooks/hard-eng.py check --plan-stage Ready --base origin/develop` passed.
E2E: N/A — no user journey; the coordinator's behavior is proven by its script tests.
Retro: these items, each sorted by HE Learn's Retro rows.
- The comment wake shipped on 2026-11-09 without a check of Trello's Automation quota against a real board's comment count; a consumer review found a real board's monthly comments several times the 250 runs a month → judgement, first occurrence: check an outside service's quota before building on it. None new.
- No step handled a `wake` left by the older release → caught by the Reader rule. None new.
- `shipped-format` refused the command table after rows were removed, and HE-NO-SWITCH-OFF asked for `Removed test:` lines → caught by the gates. None new.

Delivery target: Merge
Delivery: Pending — PR into `develop`, rebase merge, then the release PR from `develop` into `main`.
