# Trello mockups follow one standard, and picture posts need a proof file

Status: Ready

## Outcome + scope

The coordinator's design and mockup posts follow one standard: a rules brief in every design brief, a coverage table, a nothing-lost list, whole-page checks at 390 and 1280, a taps table, a real app with fake data, one combined After image for staff, and a fixed closing line. The board tool refuses a picture with no current proof file and adds the closing line to a post with a new screen. Non-goals: the planning UX guide's rules and sizes, the `move --shows` flag, pictures already on cards.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/commands.py` (`attach` uploads every picture for `comment`, `move` and `upload`; `post_comment` builds the comment text), `references/run.md` (Design approval), `references/commands.md` (command rows), `SKILL.md` (routes), `.agents/skills/he-plan/references/ux.md` (usability rules).
Same cause: N/A — a new standard, not a fix.
Single source: the nine rule names live once in `commands.py` (`UI_RULES`); the new `references/mockups.md` table lists the same names, and a test fails when they differ. The closing line lives once in `commands.py`; `mockups.md` quotes it, and the same test checks it. Shared usability rules stay in `ux.md`; `mockups.md` points to them and adds only its own rules. Searched: the skill folder, `tests/`, `.hooks/` and `.agents/skills/he-plan/` for "Design approval", "before and after" and picture rules.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-11, through a project's coordinator: "These new mockups with the flows, can we add that as a standard one for trello"; rebase on the current base first; publication privacy before push; normal PR flow. Merge when green per the standing rule.
Decision: one reference, `mockups.md`, loaded only for design work. The proof gate sits in `attach`, so every picture post (`comment --image`, `move --proof`, `upload`) needs a proof file beside the picture (`<picture>.json`), checked for all pictures before the first upload, `--dry-run` included. A picture that shows no new screen uses `notNewUi` with a reason. The tool adds the closing line after the pictures when a posted picture's proof has `uiRules`. The staff image drops Before; the plan and the pull request still keep the real Before per `ux.md`. Testing-move proof keeps before and after. 44 px is this standard's own minimum; `ux.md` keeps 24 px for other work. The taps table goes in the worker's report and the card's plan, never in the staff image.

## Acceptance + steps

- [ ] A picture with no proof file, a proof older than the picture, a proof without `change`, `shows` and `showsChange: true`, or a proof missing a rule line of at least 20 characters is refused before any upload, dry run included; the error names the file and the missing keys → `tests/test_trello_coordinator.py::test_a_picture_needs_a_current_proof_file`.
- [ ] A proof with all nine rule lines, or with a `notNewUi` reason, passes; a file that is not a picture needs no proof → `tests/test_trello_coordinator.py::test_a_picture_needs_a_current_proof_file`.
- [ ] A comment with a new-screen picture ends with the bold closing line after the pictures; a comment whose pictures are `notNewUi` does not → `tests/test_trello_coordinator.py::test_a_new_screen_post_ends_with_the_closing_line`.
- [ ] The rule names and the closing line in `mockups.md` match the tool → `tests/test_trello_coordinator.py::test_mockup_rules_match_the_proof_gate`.
- [ ] Real board: on a test card, a picture with no proof is refused; with a proof it posts with the closing line; both are then removed → manual check with the fixed tool, result recorded here.

## Baseline + execution

Result: Passed
Evidence: develop 7c3c9760 passed its Hard Eng, Canary, PR text and Release source runs on 2026-11-11; `check --plan-stage Draft --base origin/develop` passed (exit 0) with only this plan changed. On that code the three new tests failed: no rule list in the tool and no `mockups.md`.
Execution: one session; failing tests first, then the gate, the closing line and the reference; one Reader pass on the new text; then the checks, the review and the real-board check.

## Risks + recovery

After the next Hard Eng update, every picture post on every board needs a proof file, testing moves included; a coordinator that does not write one is refused until it does. The refusal names the file, the missing keys and `mockups.md`. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change; this changes the coordinator's rules and its board tool.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey; the tests run the real script against a fake Trello, and one real-board check covers the live path.
Retro: Pending.

Delivery target: PR
Delivery: Pending — PR into develop, then the release to main.
