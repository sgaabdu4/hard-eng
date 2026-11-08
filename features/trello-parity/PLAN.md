# The Trello coordinator sees and does what a mature coordinator does

Status: Complete

## Outcome + scope

The board tool reports every human action and open question, and its writes keep labels, members, checklists and card numbers right, as a mature coordinator in production does. Non-goals: editing our own comments (the tool still never edits), the items under Not in scope, and any change to app screens.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/board.py` (reads actions into events), `report.py` (the `check` lists), `commands.py` (write commands), `config.py` (card text checks), `api.py` (Trello replies), `SKILL.md` and `references/run.md`, `references/commands.md`, `references/hosts.md`. Tests: `tests/test_trello_board.py`, `tests/test_trello_coordinator.py`, fakes in `tests/trello_fakes.py`.
Same cause: rules a mature coordinator learned in production did not reach this tool. The earlier fix of this cause is `features/trello-picture-lines/PLAN.md` (helped: pictures in one comment now each show). This plan covers every other gap found by a rule-by-rule audit of that coordinator against this skill and its scripts.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-08 approved the audit's fix list and, with "ok", this plan's decisions: "yes pls but ignore the editing old comment one". Scope = audit items 1-10 and 12-19, plus the open half of the picture rule. Item 11 is out: the tool keeps "never edits".

Decision: remove `quietHours` and `timeZone`; the owner asked for posts at any hour.
Decision: card numbers: a card without `#N`, and the newer card (higher card id, which carries its creation time) of two open cards with the same `#N` (Trello copies keep the name), get the next free number: the highest `#N` on any card, archived included, plus one. This is the rule `new` already uses. Trello's own short id is not used, because on a board numbered by hand it can equal a number another card already has.
Decision: open checklist items block a move to `testing` or `done`. The command names the open items; `tick` closes one once it is proven.
Decision: work with no screen still goes to `testing`, so it reaches staging and a tester like any card. It needs `--check TEXT`, a written note of what to try, in place of `--proof`. A card that changes a screen still needs before and after pictures.
Decision: links to other cards are checked by the script, not by a prose rule: `comment` and `new` refuse a card link that is not on the board.
Decision: the "Unsupported image" half of the picture rule gets no check after posting. Trello's API can show the comment text and the attachment's file type, but not how the comment renders. The text is already right by construction, and the earlier fix found the file types already right. So `upload` only prints its image lines joined with blank lines.

## Acceptance + steps

Slice 1: the report sees every human action

- [x] A card move or a new card by a board member is a request; by anyone else it is information → `tests/test_trello_board.py::test_people_moves_and_new_cards_are_requests` (`board.py` keeps `move` and new `created` events from others; `report.py` excerpts "[moved to <list>]" and "[made the card]").
- [x] A move or new card by the token's account that our `move` or `new` did not make is an `owner` item; after each write, `move` and `new` read the card's newest move or create action once and append its id to the posted log (`commands.py`, `report.py`) → `tests/test_trello_board.py::test_owner_moves_and_cards_not_made_by_the_tool_are_owner_items`.
- [x] An edited comment replaces the old text and counts at its edit time, so an edit after our reply is a request → `tests/test_trello_board.py::test_edited_comment_counts_at_its_edit_time` (`board.py` reads `data.dateLastEdited` on `commentCard` actions; Trello logs no separate edit action, checked on a real board on 2026-11-08; an edit moves the card's `dateLastActivity` but not the action's date, so `board.py` also reads the `commentCard` actions of each card active since the last check and takes those edited after it).
- [x] A short reply such as "ok", "thanks", "works" or "done" (tags allowed) on a card in `done` is not a request; on an open card it still is (`report.py`) → extend `tests/test_trello_coordinator.py::test_done_card_requests_expire_after_the_grace_hours`.
- [x] The newer of two open cards with the same `#N` (higher card id) is listed in `unnumbered` as a duplicate (`report.py`) → `tests/test_trello_board.py::test_duplicate_numbers_are_listed_and_refused_as_a_card_reference`.
- [x] A card reference `#N` that matches two cards is refused with both shortLinks, so no write reaches the wrong card (`commands.py`) → `tests/test_trello_board.py::test_duplicate_numbers_are_listed_and_refused_as_a_card_reference`.
- [x] `update <card> --renumber` names the card `#<next free number> <title>` (`commands.py`) → extend `tests/test_trello_board.py::test_update_renames_and_sets_the_due_date`.

Slice 2: open questions and chasing

- [x] An open question = any of our comments that tags a person and asks something, with no comment from that person after it, even when newer comments of ours do not tag them. `board.py` keeps our comments back to the oldest open question; `report.py` reads them → extend `tests/test_trello_board.py::test_labels_follow_open_questions_not_any_tag`.
- [x] A hidden open question (our newest comment does not tag that person) is listed in a new `buried` list; the run asks it again in a new tagged comment (`report.py`, `references/run.md`) → `tests/test_trello_board.py::test_hidden_open_question_is_listed_as_buried`.
- [x] `silent` counts from the open question's date, not from our newest comment (`report.py`) → `tests/test_trello_board.py::test_silent_uses_the_open_question_not_the_newest_comment`.
- [x] A board member's comment that tags another member and asks something opens a question to that member: `labels` lists the missing label until they reply (`report.py`) → `tests/test_trello_board.py::test_a_member_asking_another_member_opens_a_question`.
- [x] On a `testing` card, a person whose `needsLabels` label is on the card is counted in a new `testQueue` list (one item per person: card count and oldest card) and never listed in `silent` (`report.py`) → `tests/test_trello_board.py::test_testing_cards_count_for_their_tester_and_are_not_chased`.
- [x] A promise after a "now live" or "done" part of the same comment is still a promise; only text after the last finished phrase is checked (`report.py`) → extend `tests/test_trello_board.py::test_promises_ignore_conditional_live`.
- [x] `waitsOnUs` and `promises` also match "I am building", "I am changing", "I will fix", "being built" and "waits for the #N fix"; finished also matches "went live" and "are live" (`report.py`) → extend `tests/test_trello_board.py::test_waits_on_us_ignores_conditional_live`.

Slice 3: the testing flow writes

- [x] `move <card> testing` takes `--check TEXT` in place of `--proof`; the note goes into the testing comment, and `references/run.md` says pictures stay required for any screen change → `tests/test_trello_coordinator.py::test_testing_move_takes_a_written_check_for_work_with_no_screen`.
- [x] `move <card> testing` needs `--comment FILE` that tags at least one board member. It posts one comment with the text and the proof pictures (blank lines between), and makes every tagged member a card member, adding the `needsLabels` label when one is configured (`commands.py`) → extend `tests/test_trello_coordinator.py::test_testing_move_needs_proof`.
- [x] `comment` never moves a card; the move to `doing` is explicit (`move <card> doing`, run by the coordinator, `references/run.md`), because loose wording moved released cards. `waitsOnUs` stays a report list and ignores conditional clauses and "should ...?" questions → `tests/test_trello_coordinator.py::test_a_comment_never_moves_a_card`.
- [x] `member <card> add|remove <username>` adds or removes one board member; a username not on the board is refused (`commands.py`) → `tests/test_trello_coordinator.py::test_member_adds_and_removes_a_person`.
- [x] `comment` that asks a tagged person also makes them a card member, next to the label it already adds (`commands.py`) → extend `tests/test_trello_board.py::test_comment_adds_the_needs_label_of_each_person_asked`.
- [x] `card` prints members and every checklist with each item's state (`commands.py`) → extend `tests/test_trello_board.py::test_card_prints_the_whole_card_and_hides_secrets`.
- [x] A move to `testing` or `done` with open checklist items is refused and names them; no write is sent (`commands.py`) → `tests/test_trello_coordinator.py::test_move_refuses_open_checklist_items`.
- [x] `tick <card> <item text> [--undo]` marks one checklist item done or open; no match or two matches is refused (`commands.py`) → `tests/test_trello_coordinator.py::test_tick_marks_one_checklist_item`.

Slice 4: sign-in, duplicates, text and links

- [x] A builder starts only when no open card PR touches the same files, and a card PR that conflicts after a merge is its builder's next job (`references/run.md`; parallel card builders left PRs in conflict) → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] `trello.json` `timing` no longer takes `quietHours` or `timeZone`: a file that sets either is refused with a line saying to delete it; `SKILL.md`, `references/hosts.md` and `references/commands.md` drop every quiet-hours rule (`config.py`) → extend `tests/test_trello_coordinator.py::test_config_defaults_and_role_provider`.
- [x] A 401 from Trello gives one error, "Trello refused the token: it is revoked or expired", with `tokenRefused: true`. `firstReport` is true only on the first refused run since the last good read, so the owner is told once → `tests/test_trello_coordinator.py::test_refused_token_is_reported_once` (`api.py`, `state.py`).
- [x] `references/hosts.md`: `tokenRefused` with `firstReport` → ask for a new token only, with the existing token steps → extend `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] `archive <card> --into <card>` posts one comment on the copy with the original's link read from the board, removes its `needsLabels` labels and closes it (`commands.py`) → `tests/test_trello_coordinator.py::test_archive_links_the_original_and_closes_the_copy`.
- [x] `upload` also prints one `markdown` block with the image lines joined by blank lines (`commands.py`) → extend `tests/test_trello_coordinator.py::test_label_upload_and_download_use_the_card_endpoints`.
- [x] A bold first line may follow one or more `@tags` on the same line → extend `tests/test_trello_board.py::test_card_text_must_be_short_and_laid_out` (`config.py`).
- [x] `comment` and `new` refuse a Trello card link whose shortLink is not on the board, archived cards included (`commands.py`) → `tests/test_trello_board.py::test_comment_refuses_links_to_cards_not_on_the_board`.
- [x] `SKILL.md` Core rules gain two short lines: replies sound like a person (vary the wording, no fixed opener); work with no screen goes to `testing` with `--check`, never without a note → extend `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] `references/commands.md` documents `member`, `tick`, `archive`, `update --renumber`, `move --comment`, the `upload` block and the `buried` and `testQueue` lists; `references/run.md` adds their actions → extend `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`. Each slice updates this test, `WRITE_COMMANDS`, the doc rows and `report.FIELDS` (same order as the doc table) for its own commands and lists, so the test passes after every slice: slice 2 adds `buried` and `testQueue`, slice 3 adds `member` and `tick`, slice 4 adds `archive`.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` passed on 2026-11-08 at develop 4a5b0f3c, which passed required CI.
Execution: one Sonnet builder, slices 1 to 4 in order, failing test first for each checkbox, the full check after each slice. A fresh Opus reviewer reads the whole diff before merge. Built in order: slice 2 needs slice 1's event changes, and slice 3 reuses slice 2's phrases. When a test file would pass the HE-FILE-LENGTH limit, the new report tests move to `tests/test_trello_report.py`.

## Risks + recovery

- `move <card> testing` changes shape: it needs `--comment FILE`. A coordinator that still runs `move` then `comment` gets a clear refusal and follows the updated `references/run.md`.
- Hard checklist blocks can stall an automatic release. The refusal names the open items, so the coordinator ticks proven ones or asks.
- Edit, move and create shapes were read from a real board on 2026-11-08: an edited comment keeps its `commentCard` action and gains `data.dateLastEdited`; a move is `updateCard` with `data.listBefore`/`listAfter`; a new card is `createCard`. Fakes copy those shapes. A board read may need `filter` to include `createCard`.
- Keeping our comments back to the oldest open question makes the saved state larger on long threads. It stays bounded, because a reply from the person ends that question.
- Hard checklist blocks could stop a real release move. Recovery: `tick` the proven items; nothing else bypasses the check.
- Recovery for any slice: revert that slice's commits; each slice passes the gate alone.

## ux_reference

N/A — no app screens change; the tool writes only Trello comment text, labels, members and checklists.

## Verification

Result: Passed
Evidence: every box ticked after its named test failed first and then passed; `python3 .hooks/hard-eng.py check --plan-stage Ready --base origin/develop` passed after each of the four slices and the edit-read fix (full suite 2333 tests); review findings (explicit move to doing, chase clock, tester labels, conditional clauses, own edits) each got a failing test first; `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` passed on the final code after them. A read-only call on a real board on 2026-11-08 showed that an edit moves the card's `dateLastActivity` and keeps the action date.
E2E: N/A — the tool is a command line program; the tests drive its real `main` end to end against a Trello fake built from real replies, and runs may not call Trello.

Delivery target: PR
Delivery: Pending — one PR into develop, merged on green.

Not in scope: a label for cards that wait on a real event (project-specific); editing our own comments (item 11); a check after posting that no "Unsupported image" shows; and the smaller gaps: overlap on the read window, sorting columns, listing unnamed labels, merging out-of-date testing cards after a release, a block on open requirement questions, a list of doing cards that wait on people, a check that each running worker's card is in doing, a proof check on plain comment pictures, a block on direct API calls around the tool, and labels, members or due dates on `new`.
