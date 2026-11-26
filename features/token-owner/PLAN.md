# One owner of "is this value a token", and no colour from a constant name

Status: Ready

## Outcome + scope

`look` stops judging a colour, a gap or a radius against the DESIGN.md token lists. HE-UI-SOURCE reads the source code, so it stays the one owner of the token rule. Code in `look` decides only whether a stated claim is true: square or rounded, touch, centred, bolder or lighter than, tap size and text size. A value that no token list holds goes to the reviewer, who can dispute it. The facts list names no value to copy. `look` no longer loads PyYAML. A JS constant named like a colour, such as `WHITE`, is no typed colour in a style object; a quoted `'white'` is, and a stylesheet still reads a name in any case. A typed style object (`const headerStyle: CSSProperties = {`) counts as a style object. Five old Complete plans that named the deleted look tests now name the tests that replace them. Non-goals: teaching `look` to read the stylesheet theme or an alpha, and any new rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-26 and the release proof of `develop` that it cites.

## Repository context

Owners: `.hooks/look_facts.py` (the facts and the verdicts), `.hooks/look_records.py` (`code_fails`, `decide_line`), `.hooks/look.py` (the prompt and the inputs), `.hooks/look_answer.py` and `.hooks/ui_measure.py` (the item kind text), `.hooks/browser.py` (the `look` entry), `.hooks/ui_raw.py` (`declaration_hits`).
Same cause: hotfix `28954402` (on `main`) removed the token verdicts from `look` for the same reason, and `5d2a8f7a` and `e141d3af` removed the token reading that only those verdicts used. The join kept develop's version of the look modules, so the second owner came back. The five look modules and the item kind text equal `main` again. Colour names in `ui_raw.py` share the cause of the second owner only in spirit: the value was lowered before it was matched, so a constant looked like a colour; that is a separate fault with its own commit.
Single source: HE-UI-SOURCE (`ui_whole.py`, `ui_tokens.py`) for every token verdict. Kept on purpose: `ui_tokens.py` and the PyYAML load of `ship`; both are used by the whole-project scan and by `ship`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the maintainer's release request to merge to develop and main; the coordinator's brief of 2026-11-26 asks for this fix, and the coordinator merges the PR into `develop` through `ship`.

## Acceptance + steps

- [x] A gap and a radius outside the token lists stay reviewer items, a colour item is refused with the judgement tag named, the facts list names no value that invites a token item, and the prompt describes no check against the token lists → `tests/test_look_no_token_verdicts.py::test_a_gap_and_a_radius_outside_the_token_lists_stay_with_the_reviewer` and `tests/test_look_no_token_verdicts.py::test_a_colour_item_outside_the_token_list_is_refused_not_decided` and `tests/test_look_no_token_verdicts.py::test_the_facts_list_no_value_that_invites_a_token_item` and `tests/test_look_no_token_verdicts.py::test_the_prompt_describes_no_check_against_the_token_lists`
- [x] Every claim-truth verdict is kept: touch, square, centred, weight, tap and size → `tests/test_look_no_token_verdicts.py::test_a_chips_touch_claim_stands_at_0_px_and_falls_at_4_px` and `tests/test_look_facts.py::test_code_decides_each_measured_kind` and `tests/test_ui_corner_facts.py::test_square_chips_are_recorded_and_decided_from_their_own_corners`
- [x] A colour name in a style object counts only as a quoted string; a stylesheet reads it in any case → `tests/test_ui_raw_forms.py::test_a_colour_name_in_a_style_object_counts_only_as_a_quoted_string`
- [x] `ship` still loads the PyYAML runtime → `tests/test_tool_environment.py::test_ship_loads_the_yaml_runtime_before_it_runs`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`88380e13`) the look, UI-source and audit tests pass (574 cases). The new look tests fail there: 4 of 7 in `tests/test_look_no_token_verdicts.py`, each on a real assertion (a code verdict that the reviewer should hold, a value in the facts list, token text in the prompt). The colour-name rows fail there: 4 of 9; the other 5 guard quoted names, a template hole and a stylesheet.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then one commit for the look removal and one for the colour-name fix.

## Risks + recovery

A project with a reviewer Fail on a value that a token list lacks now keeps it as a reviewer item; the whole-project scan of HE-UI-SOURCE still refuses a typed value outside the theme. A JS object that is not named like a style (a helper that returns an object, a chart config) still reads an unquoted constant as a colour; that is a stated limit of the style-object reader, as before. A name in a real quoted string, a template string with a `${` after it, a `[color:white]` class and a stylesheet is still found. Recovery: revert the two commits.

## ux_reference

N/A — hook validation logic and tests only; no visible UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — hook tests run real temporary Git repositories and real file text; no user journey changes.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
