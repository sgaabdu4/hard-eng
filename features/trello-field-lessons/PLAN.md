# Trello coordinator lessons from a long-running board

Status: Complete

## Outcome + scope

A coordinator that ran a busy board for weeks found four gaps the skill does not cover. Cards that only a real customer event can prove were forgotten. Proof images showed the right screen without the change. Tagged people had no Needs label, so their questions were lost. A save feature passed every test but never saved on a real server. Now `check` lists cards waiting for a real event, a testing move names what each proof image shows, `comment` adds the Needs label for each tagged person asked a question, and a new or changed save needs one real save on a deployed test environment before the testing move. Worker briefs may not narrow a Hard Eng check, a ready card is released without waiting for a bigger batch, and the planning guide counts a job that falls behind as stopped. Non-goals: reusing idle worker threads for other jobs (follow-ups on one card already go to the same worker, and a cold thread can cost more than a new one), card membership, extra columns, a per-project label name.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (check report), `commands.py` (comment, move, label), `.agents/skills/he-plan/references/ux.md` (job states), `references/run.md` (report lists, workers), `references/commands.md` (contract).
`report.FIELDS` and the commands table are checked against the reference text by `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.
Same cause: each gap was a rule the coordinator had to remember with nothing in the script or run rules to make it happen.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "yes", with a test on a real project's board and staging before release; merge after green checks for the coordinator work. Abid on 2026-11-07: "yes go for it" to the brief, batch and falls-behind rules.
Decision: the real-event label name is fixed, `Waiting for real case`; no new `trello.json` field.
Decision: `--shows` text becomes the attachment name, so the caption sits under the image on the card.
Decision: adding `Waiting for real case` creates it on the board when missing; every other missing label is refused.
Decision: labels only, no card membership; the `labels` report row already lists labels to remove.
Decision: the real-save rule lives in the coordinator's worker review, not in the general testing guide.
Decision: before release, the branch's skill runs from an uncommitted copy in a scratch checkout of a real project, against its real board (writes as `--dry-run`), plus one real save on that project's test environment.

## Acceptance + steps

- [x] `check` lists open cards with the `Waiting for real case` label in `realCases`; done cards are left out → `tests/test_trello_coordinator.py::test_check_reports_every_missed_item`.
- [x] A testing move needs one `--shows` per `--proof`, refuses private data in it and uses it as the attachment name → `tests/test_trello_coordinator.py::test_testing_move_needs_proof`.
- [x] A comment that asks a tagged person adds that person's Needs label once; a comment with no question adds none → `tests/test_trello_board.py::test_comment_adds_the_needs_label_of_each_person_asked`.
- [x] Adding `Waiting for real case` creates the missing label, another missing label is refused → `tests/test_trello_coordinator.py::test_label_upload_and_download_use_the_card_endpoints`.
- [x] The run rules state the real-event loop, the real-save proof, briefs that never narrow a Hard Eng check and release without batching → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] The planning guide counts a job that falls behind as stopped → N/A — planning guidance wording; no checker reads it.

## Baseline + execution

Result: Passed
Evidence: develop at the branch point passed required CI; `python3 .hooks/hard-eng.py check --plan-stage Draft` passed on 2026-11-07; the four new tests failed before the change.
Execution: one session; failing tests first, then the real-board trial (`check`, `comment --dry-run` and `move testing --dry-run` from the branch copy give the expected lists and planned writes; one real save on the test environment is read back and removed), then the PR.

## Risks + recovery

`comment` now writes a label after the post; a missing Needs label is skipped, never created. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change; card text rules are unchanged.

## Verification

Result: Passed
Evidence: Trello suites 70 passed; real-board trial from an uncommitted copy in a real project: `check` gave every list (`realCases` empty), `comment --dry-run` planned the Needs label, `move testing` without `--shows` was refused and with it planned the caption, `label add "Waiting for real case" --dry-run` planned the label; that project's staging journeys rerun in CI passed 12 of 12, with real saves read back and removed; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey; the fake Trello server tests run the real script, and the real-board trial covers the live API.
Delivery target: PR
Delivery: Pending — PR into develop.
