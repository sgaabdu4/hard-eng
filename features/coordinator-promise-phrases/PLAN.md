# Coordinator promise check catches present-tense plans

Status: Complete

## Outcome + scope

The trello-coordinator `promises` list now catches a promise written in plain present tense ("I post here when the store answers") and more "I am …ing" forms, and it ignores the question part of any sentence, so "Can I check it?" is never a promise while "I'll post it tonight, can you test it?" still is. Non-goals: the `waitsOnUs` phrase list, other report lists, and any consumer's own rules.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (`INTENT`, `PROMISE`, `CONDITION`), `references/commands.md` (`promises` and `waitsOnUs` rows); test in `tests/test_trello_board.py`.
Bug evidence: a map for moving a consumer coordinator to this skill ran its open promises through `PROMISE`; about half did not match, because that coordinator writes plans in plain present tense, as ASD-STE100 asks. Two made-up sentences of that form returned no match on `develop` dbb5badf.
Same cause: the parity work copied only part of the consumer's promise words; the present-tense forms and the longer "I am …ing" list were left out. The fix widens the one `PROMISE` pattern; no second list.
Single source: the promise words live in `report.INTENT` and `report.PROMISE` only. `commands.md` describes them in its `promises` row; no other code copy. `WORKING` stays shared by `PROMISE` and `WAITS`. Searched `.agents/skills/trello-coordinator/` and `tests/` for `PROMISE`, `WORKING` and `should ...?`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: the maintainer approved this route on 2026-11-10: fix the promise check first, then the consumer's own gaps, a read-only trial and one switch.
Decision: present tense counts only for first-person verbs that announce our own next step (check, post, make, fix, send, add, update, tell, share, reply, look, watch, test). Move, tag and confirm are left out, because "I move this card to Testing" and "I confirm the crash is gone" describe what the comment itself does. Past tense never matches, because each verb ends at a word boundary.
Decision: the question part of a sentence, from its last comma or semicolon to the "?", is hidden before the promise and live checks, not only "should …?" questions. An offer such as "Shall I post the steps?" waits for a reply; a promise before the comma, as in "I'll post it tonight, can you test it?", still counts.
Decision: `waitsOnUs` keeps its phrase list. Widening it would move more testing cards back to doing; no report asked for that.

## Acceptance + steps

- [x] Present-tense and "I am …ing" plans count as promises; past tense, questions and lines that describe the comment's own action do not; existing cases keep their result → `tests/test_trello_board.py::test_promises_ignore_conditional_live` (8 new promise cases, 7 new non-promise cases).
- [x] A question after a comma hides only its own part, for the waits list too → `tests/test_trello_board.py::test_waits_on_us_ignores_conditional_live` (2 new cases).
- [x] The reference rows match the code → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: `develop` dbb5badf passed Canary, Release source and PR text on 2026-11-10; its Hard Eng run was still going when this branch started.
Execution: this session, one builder.

## Risks + recovery

- A first-person present-tense line that only describes, such as "I check this every day", now shows as a promise. Recovery: the coordinator answers it as done or posts a new time, the same as any promise.
- A question with no comma before it is hidden whole, so a promise inside it, such as "Shall I post it tonight?", does not count. That is the intended reading: an offer waits for a reply.

## ux_reference

N/A — no app screens; coordinator script and reference text only.

## Verification

Result: Passed
Evidence: On 2026-11-10 the new cases failed first: 6 of 6 promise cases listed no promise on `develop` dbb5badf. A Reader pass then found that hiding a whole question sentence dropped "I'll post it tonight, can you test it?" and "I am fixing the crash now, can you send the log?", which `develop` caught, and that move, tag and confirm listed descriptions as promises; those 7 cases failed before the second fix. The Reader's reworded `promises` row and its three older mismatches ("are done" and "now" forms, "waits for the #N fix", how far a conditional reaches) were fixed. After the fixes: `tests/test_trello_board.py`, `tests/test_trello_report.py`, `tests/test_trello_coordinator.py` (139) passed; ruff format and lint passed; `biome ci` with `.agents/biome.json` passed; jscpd found 0 clones.
E2E: N/A — the script has no user journey; the fake board tests run the real `check` command.
Retro: these items, each sorted by HE Learn's Retro rows.
- Bug found on the base branch: the promise check missed present-tense plans → mechanical: new cases in `tests/test_trello_board.py::test_promises_ignore_conditional_live`, the gate that should have caught it.
- The Complete check failed `duplicates`: the first fix added a second test with the same body → caught by the gate; the cases moved into the existing test. None new.
- The Reader pass found a regression in the first fix (a whole question sentence was hidden) → caught by the Reader rule; fixed before push with failing cases first. None new.
- User correction: "I feel like you haven't followed everything we decided" → judgement: an approved later step was dropped across several summaries; the open-items list now comes from every "still open", "pending" and "not done" line in the transcript, not from memory. None new in Hard Eng.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
