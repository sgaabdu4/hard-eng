# Trello setup with the least manual work

Status: Complete

## Outcome + scope

When `.env.trello.local` lacks the Trello key or token, a T3 Code coordinator asks for each one in the secret popup with exact steps, and the script saves it to the main checkout's ignored file, where every worktree finds it. Claude Code and Codex have no popup: the coordinator stops and gives the same steps. Setup needs only the board link: lists are found by name, the account comes from the token, every board member may make requests, workers use the host's default models, `save-secret` makes git ignore the file locally, and a T3 coordinator schedules itself on its first run. Non-goals: OAuth, a Trello login flow, copying the file into worktrees, automatic Needs labels.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/secrets.py` (file location + ignore check), `commands.py` (CLI), `references/hosts.md` (per-host steps), `references/commands.md` (command contract).
Same cause: N/A — new capability on the merged coordinator skill.
Source evidence: Trello developer docs, API introduction and managing apps pages (admin page https://trello.com/apps/admin, New, "My app doesn't use Power-Up capabilities", Trello Auth tab, Generate a new API Key, Token link, Allow).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-05 said "go" in chat for popup + automatic save, saved in the main checkout for all worktrees, with super clear steps in the popup; then "We need to automate as much as possible".
Decision: new `save-secret` command reads the popup's file and writes only after git ignores the file; it runs without a key or token, prints the name only and keeps the file readable by its owner only.
Decision: popup text lives word for word in `hosts.md`, key first, then token.

## Acceptance + steps

- [x] From a worktree, `save-secret` writes the key and token into the main checkout's file, keeps other lines, replaces the old value, sets owner-only access and never prints the value; `probe` then works → `tests/test_trello_board.py::test_save_secret_fills_the_main_checkout_from_a_worktree`.
- [x] An empty paste or one with spaces is refused and the file is unchanged → `tests/test_trello_board.py::test_save_secret_refuses_a_bad_paste`.
- [x] A file git does not ignore is ignored through the local exclude file, with no tracked change → `tests/test_trello_board.py::test_save_secret_ignores_the_file_without_a_tracked_change`.
- [x] A tracked secrets file is never written → `tests/test_trello_board.py::test_save_secret_refuses_a_tracked_file`.
- [x] `trello.json` with only a board link works: lists by name, account from the token → `tests/test_trello_board.py::test_a_board_link_alone_is_enough`.
- [x] A board without a needed list names the missing role → `tests/test_trello_board.py::test_a_board_without_a_needed_list_names_it`.
- [x] Without `allowed`, every board member makes requests and others give information → `tests/test_trello_board.py::test_without_allowed_every_board_member_makes_requests`.
- [x] The documented command matches the CLI → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: develop 925292d7 passed required CI (Hard Eng and Canary runs after PR 494 merged).
Execution: one session; failing tests first.

## Risks + recovery

A pasted token reaches the whole Trello account → saved only in the ignored file, never printed; revoke it in Trello account settings if exposed.

## ux_reference

N/A — popup text only; no app screen changes.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0; 80 focused coordinator, board, routing and skill link tests passed.
E2E: N/A — the popup needs a person to paste a real token; the script path from popup file to `probe` is covered by the worktree test above.
Delivery target: PR
Delivery: Pending — PR into develop.
