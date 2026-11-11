# Trello coordinator lists open cards nobody has touched

Status: Ready

## Outcome + scope

A real coordinator run showed two cards stuck for days. One sat in Doing after its question was answered; the other sat in To do after the card it waited for was finished. No report list named them: the lists only react to new comments, promises, questions and labels, and neither card had any. Now `check` adds an `idle` list: each card in To do, Doing or Urgent with no comment or move for `chaseHours`. A Workers rule in the run steps says what to do with each listed card: check its worker for a stall, ask a person once or record what it waits for, close it, or start it. Non-goals: chasing people (the `silent` and `buried` lists), Discuss cards, a new setting.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (report lists), `references/run.md` (actions per list), `references/commands.md` (report fields).
Bug evidence: on one board, a Doing card stayed 5 days after its answer and a To do card stayed 5 days after its blocker closed; both had no new comments, so every run reported a clean board.
Same cause: Urgent cards are open work too, so they are listed; Discuss cards hold talk, which `silent` and `buried` already chase. The card's own last-activity time cannot be the clock: a board script that re-sorts or relabels cards bumps it on every run (seen on a second board, where every open card showed activity within the hour), so the clock is the newest comment or move in the snapshot, then the creation time in a real card id, then the last-activity time.
Single source: the wait limit reuses `timing.chaseHours`; the list names come from `config.lists` roles; a search of the skill, its tests and `references/` for the report field names found `FIELDS` in `report.py`, the `run.md` table and the `commands.md` report section, all updated here.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-11 reported the coordinator error with the run that missed the two cards; merge after green checks for the coordinator work.
Decision: one list, `idle`, with the same item shape as the other lists; one Workers rule beside the start rule owns its action, so starts keep the capacity, approval and shared-file rules; the start rule now says "free worker capacity", so "idle" names only the list; `handover.md` now records what each card waits for.

## Acceptance + steps

- [ ] A To do, Doing or Urgent card with no comment or move for `chaseHours` is listed, with its hours and list → `tests/test_trello_report.py::test_an_open_card_nobody_touched_is_listed_as_idle`.
- [ ] A recent comment or move keeps an open card off the list, and Testing, Done and Discuss cards are never listed → `tests/test_trello_report.py::test_a_recent_comment_or_move_keeps_an_open_card_off_the_idle_list`.
- [ ] A script that bumps the card's last-activity time does not hide an idle card → `tests/test_trello_report.py::test_a_bumped_last_activity_does_not_hide_an_idle_card`.
- [ ] Every report list, `idle` included, has an action row in the run rules → `tests/test_trello_coordinator.py::test_every_report_list_has_a_run_action`.

## Baseline + execution

Result: Passed
Evidence: develop 2f103be9 passed its Hard Eng, Canary, PR text and Release source runs on 2026-11-11.
Execution: one session; failing tests first, then the list, the rule row and a read-only replay on a real board.

## Risks + recovery

A board with many open cards that rightly wait lists them on every run. Recovery: the coordinator records each wait in `handover.md` and sends no message; revert this pull request if the list is noisy.

## ux_reference

N/A — no app screens change.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey; the report tests run the real script against a fake Trello.
Delivery target: PR
Delivery: Pending — PR into develop.
