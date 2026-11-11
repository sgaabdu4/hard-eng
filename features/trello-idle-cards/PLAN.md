# Trello coordinator lists open cards nobody has touched

Status: Ready

## Outcome + scope

A real coordinator run showed two cards stuck for days. One sat in Doing after its question was answered; the other sat in To do after the card it waited for was finished. No report list named them: the lists only react to new comments, promises, questions and labels, and neither card had any. Now `check` adds an `idle` list: each card in To do, Doing or Urgent with no comment or move for `chaseHours`. A Workers rule in the run steps says what to do with each listed card: check its worker for a stall, ask a person once or record what it waits for, close it, or send it to its worker or start one. Non-goals: chasing people (the `silent` and `buried` lists), Discuss cards, a new setting.

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

A board with many open cards that rightly wait lists them on every run, and its first run can tag each person a card waits on. Recovery: a wait on a card or a release is recorded in `handover.md` with no message; a wait on a person gets one tagged comment, then `silent` chases it; revert this pull request if the list is noisy.

## ux_reference

N/A — no app screens change.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey; the report tests run the real script against a fake Trello.
Retro: these items, each sorted by HE Learn's Retro rows.
- Bug found on the base branch (user report): an open card with no new comment was never listed → the report tests are the gate that should catch it: `tests/test_trello_report.py::test_an_open_card_nobody_touched_is_listed_as_idle` failed on develop 2f103be9 (no `idle` field) and passes now; mechanical: `tests/test_trello_coordinator.py::test_every_report_list_has_a_run_action` fails when a report list has no run action.
- The Stop hook and `check --quick` stopped on "plan is Draft": code changed before the plan was set to Ready; the same stop happened earlier on the same day in another project → caught both times by the existing check before any push; HE Plan's Readiness rule already sets that order. None new.
- The Ready check's tests step hit its 600-second limit with failures and errors near the end, while checks from other sessions kept the load average at 58 to 71 → the same suite then passed alone: 2,684 tests in 469 s, run without coverage and without the step limit. Not reproduced, so no cause found. None until it recurs.
- Reader passes 1 to 4 found ways the new rule could leave a card stuck, skip its tester, message a busy worker every hour or start a second worker → caught by the Writing Great Skills Reader rule; fixed before push. None new.
- Review corrections: the Risks line still said no message after the rule began to tag people, and no test covered a card that only we commented on → caught by review before push; the second case is now in `tests/test_trello_report.py::test_a_recent_comment_or_move_keeps_an_open_card_off_the_idle_list`. None new.
- The independent review at 6fc3bdaf found two: an image or a description edit reset the clock, though the docs name only comments and moves; and a card with an open question to a person had no clear branch → caught by the challenge before push; `tests/test_trello_report.py::test_a_bumped_last_activity_does_not_hide_an_idle_card` failed with both events and passes now, and the rule says such a card waits for `silent`. None new.
- My slips: a types run on the skill script outside the gate's own paths, and a replay started from a worktree whose main checkout holds no key → outside cause. None.

Delivery target: PR
Delivery: Pending — PR into develop.
