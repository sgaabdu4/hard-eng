# Trello mockups follow one standard, and picture posts need a proof file

Status: Complete

## Outcome + scope

The coordinator's design and mockup posts follow one standard: a design brief per the planning UX guide, a coverage table, a nothing-lost list, whole-page captures at 390 and 1280, a taps table, a real app with fake data, one combined After image for staff, nine proof rules per picture and a fixed closing line. The board tool refuses a picture with no current proof file and adds the closing line to a post with a new screen. Non-goals: the planning UX guide's rules and sizes, the `move --shows` flag, pictures already on cards.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/commands.py` (`attach` uploads every picture for `comment`, `move` and `upload`; `post_comment` builds the comment text), `references/run.md` (Design approval), `references/commands.md` (command rows), `SKILL.md` (routes), `.agents/skills/he-plan/references/ux.md` (usability rules).
Same cause: N/A — a new standard, not a fix.
Single source: the nine rule names live once in `commands.py` (`UI_RULES`); the new `references/mockups.md` table lists the same names, and a test fails when they differ. The closing line lives once in `board.py`, beside the question pattern, which skips it; `mockups.md` quotes it, and the same test checks it. The usability rules, the brief rule and the tap sizes stay in `ux.md`; each proof rule row points to the `ux.md` rules it checks, the same test fails when a quoted rule name is not in `ux.md`, and `mockups.md` adds only coverage, whole page, nothing lost and the messaging-app icon. Posting details moved from `run.md` to `mockups.md`, so `run.md` is shorter than before. Searched: the skill folder, `tests/`, `.hooks/` and `.agents/skills/he-plan/` for "Design approval", "before and after" and picture rules.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-11, through a project's coordinator: "These new mockups with the flows, can we add that as a standard one for trello"; rebase on the current base first; publication privacy before push; normal PR flow. Merge when green per the standing rule.
Decision: one reference, `mockups.md`, loaded for design work and picture posts. The proof gate sits in `attach`, so every picture post (`comment --image`, `move --proof`, `upload`) needs a proof file beside the picture (`<picture>.json`), checked for all pictures before the first upload, `--dry-run` included. `change` names what the picture proves, so an evidence picture needs no false claim. A picture with no new or changed screen uses `notNewUi` with a reason. The tool adds the closing line after the pictures when a posted picture's proof has `uiRules`; the closing line never makes our comment count as a question. The staff image drops Before; the plan and the pull request still keep the real Before per `ux.md`. A testing-move picture holds before and after side by side. The proof keys are the nine names the owner gave; their meaning comes from `ux.md`. The design brief carries the worker output list, so the rules reach the worker. The taps table goes in the worker's report and the card's plan, never in the staff image.

## Acceptance + steps

- [x] A picture with no proof file, a proof older than the picture, a proof without `change`, `shows` and `showsChange: true`, or a proof missing a rule line of at least 20 characters is refused before any upload, dry run included; the error names the file and the missing keys → `tests/test_trello_pictures.py::test_a_picture_needs_a_current_proof_file`.
- [x] A proof with all nine rule lines, or with a `notNewUi` reason, passes; a file that is not a picture needs no proof → `tests/test_trello_pictures.py::test_a_picture_needs_a_current_proof_file`.
- [x] A comment with a new-screen picture ends with the bold closing line after the pictures; a comment whose pictures are `notNewUi` does not → `tests/test_trello_pictures.py::test_a_new_screen_post_ends_with_the_closing_line`.
- [x] The rule names and the closing line in `mockups.md` match the tool, and each planning UX rule name it quotes exists in `ux.md` → `tests/test_trello_pictures.py::test_mockup_rules_match_the_proof_gate`.
- [x] Our comment with the closing line and a tag but no question is not chased: not in `silent`, `buried`, `badTags` or `labels` → `tests/test_trello_report.py::test_the_closing_line_does_not_make_our_comment_a_question`.
- [x] Real board: on a test card, a picture with no proof is refused; with a proof it posts with the closing line; both are then removed → N/A — a test cannot post to a real board. Manual check on 2026-11-11 with the fixed tool: refused with "No proof file", then posted with the closing line after the picture; comment and picture removed.

## Baseline + execution

Result: Passed
Evidence: develop 7c3c9760 passed its Hard Eng, Canary, PR text and Release source runs on 2026-11-11; `check --plan-stage Draft --base origin/develop` passed (exit 0) with only this plan changed. On that code the three new tests failed: no rule list in the tool and no `mockups.md`. The branch was then rebased onto develop 22e85390 (a plan template line only). The report test failed before its fix: the comment was listed as `silent`.
Execution: one session; failing tests first, then the gate, the closing line and the reference; one Reader pass on the new text; then the checks, the review and the real-board check.

## Risks + recovery

After the next Hard Eng update, every picture post on every board needs a proof file, testing moves included; a coordinator that does not write one is refused until it does. The refusal names the file, the missing keys and `mockups.md`. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change; this changes the coordinator's rules and its board tool.

## Verification

Result: Passed
Evidence: On 2026-11-11 each new test failed first (no rule list, no `mockups.md`; the closing-line comment listed as `silent`), then passed. The Trello tests passed (141: `tests/test_trello_pictures.py`, `tests/test_trello_report.py`, `tests/test_trello_coordinator.py`, `tests/test_trello_board.py`). The Ready check ran 4 times: each of the first 3 stopped on one named finding, fixed below; the 4th had all steps passing except one types finding, fixed and rechecked (0 diagnostics). The real-board check passed as recorded in Acceptance. Three reader passes checked the new text; each real finding is fixed. The independent review at ae635388 found one item: testing posts with a new design get no closing line. Skipped: the standard names mockup posts only, and `mockups.md` ties the line to `comment`. `check --plan-stage Complete --base origin/develop` result is recorded in the pull request.
E2E: N/A — no user journey; the tests run the real script against a fake Trello, and one real-board check covers the live path.
Retro: these items, each sorted by HE Learn's Retro rows.
- The Ready check refused the coordinator test file at 1,006 lines → mechanical: the existing file-length check caught it before push; the new tests moved to `tests/test_trello_pictures.py`. None new.
- The Ready check refused the real-board acceptance line, which named no test and gave no reason why none can prove it → mechanical: the existing plan check caught it. None new.
- The types check refused an empty list in a new test → mechanical: the existing types check caught it. None new.
- Reader pass 1 found rule names copied from the planning UX guide, which had changed on develop → single source: the proof rules now point to `ux.md`, and `tests/test_trello_pictures.py::test_mockup_rules_match_the_proof_gate` fails when a quoted rule name is not in `ux.md`.
- Reader passes 2 and 3 found rules that could not reach the worker, proofs that forced a false claim for evidence pictures, and a worker that could write proof files → judgement: fixed in `mockups.md` before push; the Writing Great Skills Reader rule is the existing owner. None new.
- The advisor found that the closing line made our tagged comment count as a question → `tests/test_trello_report.py::test_the_closing_line_does_not_make_our_comment_a_question`.
- The independent review asked for the closing line on testing posts → skipped as outside the standard, reason above. None new.

Delivery target: PR
Delivery: Pending — PR into develop, then the release to main.
