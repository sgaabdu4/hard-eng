# Trello coordinator creates numbered cards

Status: Complete

## Outcome + scope

The coordinator's rules say new work found on a card goes to a new card, but the script could not create one; the trial coordinator hit this gap. A new `new <role> <title>` command creates the card at the top of the role's list with the next free `#N` number. Non-goals: card templates, checklists, members or due dates on create.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/commands.py` (CLI, list lookup shared with `move`), `references/commands.md` (contract), `references/run.md` (when to use it).
Same cause: N/A — a missing command, not a fault in an existing one.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-05: "We need to automate as much as possible", with merge after green checks for the coordinator work.
Decision: the number counts archived cards too, so a number is never reused; title and description pass the same privacy check as comments.

## Acceptance + steps

- [x] `new` posts one card at the top of the role's list as `#N title` with the next number after archived cards, prints the number and link, refuses private data and sends nothing on `--dry-run` → `tests/test_trello_board.py::test_new_card_gets_the_next_number_at_the_top`.
- [x] The documented command matches the CLI → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: develop b775f986 passed required CI (PR 495 checks).
Execution: one session; failing test first.

## Risks + recovery

A wrong card is easy to see on the board and archive. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0; 81 focused coordinator, board, routing and skill link tests passed.
E2E: N/A — a real board write needs the private key; the fake board is built from recorded API shapes.
Delivery target: PR
Delivery: Pending — PR into develop.
