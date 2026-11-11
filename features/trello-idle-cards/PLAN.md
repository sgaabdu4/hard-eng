# Trello coordinator lists open cards nobody has touched

Status: Complete

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

- [x] A To do, Doing or Urgent card with no comment or move for `chaseHours` is listed, with its hours and list → `tests/test_trello_report.py::test_an_open_card_nobody_touched_is_listed_as_idle`.
- [x] A recent comment or move keeps an open card off the list, and Testing, Done and Discuss cards are never listed → `tests/test_trello_report.py::test_a_recent_comment_or_move_keeps_an_open_card_off_the_idle_list`.
- [x] A script that bumps the card's last-activity time does not hide an idle card → `tests/test_trello_report.py::test_a_bumped_last_activity_does_not_hide_an_idle_card`.
- [x] Every report list, `idle` included, has an action row in the run rules → `tests/test_trello_coordinator.py::test_every_report_list_has_a_run_action`.

## Baseline + execution

Result: Passed
Evidence: develop 2f103be9 passed its Hard Eng, Canary, PR text and Release source runs on 2026-11-11.
Execution: one session; failing tests first, then the list, the rule row and a read-only replay on a real board.

## Risks + recovery

A board with many open cards that rightly wait lists them on every run, and its first run can tag each person a card waits on. Recovery: a wait on a card or a release is recorded in `handover.md` with no message; a wait on a person gets one tagged comment, then `silent` chases it; revert this pull request if the list is noisy.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: On 2026-11-11 each new test failed first: no `idle` field on develop 2f103be9; the run-action test with the `idle` row removed; the bumped-clock test with an image and a description edit. Then the coordinator tests passed (137: `tests/test_trello_report.py`, `tests/test_trello_board.py`, `tests/test_trello_coordinator.py`). The full suite passed alone: 2,684 tests in 469 s, run without coverage and without the step limit. A read-only replay at a360e9bd on the reporting board planned no writes. Its two open work cards: the To do card untouched for 51 hours, which waits on a client file, is listed; the card moved to Doing an hour earlier is not. The two reported cards cannot show: the coordinator moved them by hand before the replay, one to Done and one to Doing. The larger board has no coordinator config yet, so it is not checked. Reader passes 1 to 4 and three independent reviews; each finding is in the Retro. The first Complete check stopped when its tests step reached the 600-second limit, with no failed test, at a load average of 123 to 180. The second passed at a360e9bd: 20 checks, tests in 523 s.
E2E: N/A — no user journey; the report tests run the real script against a fake Trello.
Retro: these items, each sorted by HE Learn's Retro rows.
- Bug found on the base branch (user report): an open card with no new comment was never listed → the report tests are the gate that should catch it: `tests/test_trello_report.py::test_an_open_card_nobody_touched_is_listed_as_idle` failed on develop 2f103be9 (no `idle` field) and passes now; mechanical: `tests/test_trello_coordinator.py::test_every_report_list_has_a_run_action` fails when a report list has no run action.
- The Stop hook and `check --quick` stopped on "plan is Draft": code changed before the plan was set to Ready; the same stop happened earlier on the same day in another project → caught both times by the existing check before any push; HE Plan's Readiness rule already sets that order. None new.
- The Ready check's tests step hit its 600-second limit with failures and errors near the end, at a load average of 58 to 71 from other sessions' checks; the same suite then passed alone (2,684 tests in 469 s, without coverage or the step limit). It recurred: the first Complete check hit the limit with no failed test, at a load average of 123 to 180, and the second passed in 523 s → outside cause: machine load. The 600-second limit is the project's pre-push policy, so it stays; the user decides any change. None.
- User correction "?": I held the Hard Eng check until the other project's gate ended, against the rule to run checks directly → the existing rule covers it; I started the check at once. None new.
- The foreground-wait hook refused a command that used `sleep`, and one review run started with a plain `&` that the harness could not track → caught by the hook and by me; I stopped that run and started it again as a tracked task. None new.
- Reader passes 1 to 4 found ways the new rule could leave a card stuck, skip its tester, message a busy worker every hour or start a second worker → caught by the Writing Great Skills Reader rule; fixed before push. None new.
- Review corrections: the Risks line still said no message after the rule began to tag people, and no test covered a card that only we commented on → caught by review before push; the second case is now in `tests/test_trello_report.py::test_a_recent_comment_or_move_keeps_an_open_card_off_the_idle_list`. None new.
- The independent review at 6fc3bdaf found two: an image or a description edit reset the clock, though the docs name only comments and moves; and a card with an open question to a person had no clear branch → caught by the challenge before push; `tests/test_trello_report.py::test_a_bumped_last_activity_does_not_hide_an_idle_card` failed with both events and passes now, and the rule says such a card waits for `silent`. The review at be41cb5b found that `silent` chases only our own questions, so a question from someone else left the card stuck → the rule now skips asking only when our own question is open. The review at b712086b found that a card archived during a check and then restored with no comment or move loses its comment times → skipped: it needs that rare order, and the only effect is one listing that makes the coordinator check the card's wait; the review loop stopped there, as its findings had narrowed to this edge. None new.
- My slips: a types run on the skill script outside the gate's own paths, and a replay started from a worktree whose main checkout holds no key → outside cause. None.

Delivery target: PR
Delivery: Pending — PR into develop.
