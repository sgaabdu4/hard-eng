# Coordinator promise check catches present-tense plans

Status: Complete

## Outcome + scope

The trello-coordinator `promises` list now catches a promise written in plain present tense ("I post here when the store answers") and more "I am …ing" forms, and it ignores every question, so "Can I check it?" is never a promise. Non-goals: the `waitsOnUs` phrase list, other report lists, and any consumer's own rules.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (`INTENT`, `PROMISE`, `CONDITION`), `references/commands.md` (`promises` and `waitsOnUs` rows); test in `tests/test_trello_board.py`.
Bug evidence: a map for moving a consumer coordinator to this skill ran its open promises through `PROMISE`; about half did not match, because that coordinator writes plans in plain present tense, as ASD-STE100 asks. Two made-up sentences of that form returned no match on `develop` dbb5badf.
Same cause: the parity work copied only part of the consumer's promise words; the present-tense forms and the longer "I am …ing" list were left out. The fix widens the one `PROMISE` pattern; no second list.
Single source: the promise words live in `report.INTENT` and `report.PROMISE` only. `commands.md` describes them in its `promises` row; no other code copy. `WORKING` stays shared by `PROMISE` and `WAITS`. Searched `.agents/skills/trello-coordinator/` and `tests/` for `PROMISE`, `WORKING` and `should ...?`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: the maintainer approved this route on 2026-11-10: fix the promise check first, then the consumer's own gaps, a read-only trial and one switch.
Decision: present tense counts only for first-person verbs that announce our own next step (check, post, make, fix, send, add, update, tell, share, reply, confirm, tag, look, watch, test, move). Past tense never matches, because each verb ends at a word boundary.
Decision: every question is hidden before the promise and live checks, not only "should …?" questions. An offer such as "Shall I post the steps?" waits for a reply; it is not a promise.
Decision: `waitsOnUs` keeps its phrase list. Widening it would move more testing cards back to doing; no report asked for that.

## Acceptance + steps

- [x] Present-tense and "I am …ing" plans count as promises; past tense and questions do not → `tests/test_trello_board.py::test_promises_catch_present_tense_plans` (6 promises, 4 non-promises).
- [x] Existing promise cases keep their result → `tests/test_trello_board.py::test_promises_ignore_conditional_live`.
- [x] The reference rows match the code → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: `develop` dbb5badf passed Canary, Release source and PR text on 2026-11-10; its Hard Eng run was still going when this branch started.
Execution: this session, one builder.

## Risks + recovery

- A first-person present-tense line that only describes, such as "I check this every day", now shows as a promise. Recovery: the coordinator answers it as done or posts a new time, the same as any promise.
- Hiding every question also hides a "live" word inside a question, such as "Is it live for you?", from the live checks. That is the intended reading: a question is not a statement.

## ux_reference

N/A — no app screens; coordinator script and reference text only.

## Verification

Result: Passed
Evidence: On 2026-11-10 the new test failed first: 6 of its 6 promise cases listed no promise on `develop` dbb5badf, and its 4 non-promise cases passed. After the fix: `tests/test_trello_board.py`, `tests/test_trello_report.py`, `tests/test_trello_coordinator.py` (132) passed; ruff format and lint passed; `biome ci` with `.agents/biome.json` passed.
E2E: N/A — the script has no user journey; the fake board tests run the real `check` command.
Retro: these items, each sorted by HE Learn's Retro rows.
- Bug found on the base branch: the promise check missed present-tense plans → mechanical: `tests/test_trello_board.py::test_promises_catch_present_tense_plans`, the gate that should have caught it.
- User correction: "I feel like you haven't followed everything we decided" → judgement: an approved later step was dropped across several summaries; the open-items list now comes from every "still open", "pending" and "not done" line in the transcript, not from memory. None new in Hard Eng.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
