# One owner of "is this value a token", and no colour from a constant name

Status: Complete

## Outcome + scope

`look` stops judging a colour, a gap or a radius against the DESIGN.md token lists. HE-UI-SOURCE reads the source code, so it stays the one owner of the token rule. Code in `look` decides only whether a stated claim is true: square or rounded, touch, centred, bolder or lighter than, tap size and text size. A value that no token list holds goes to the reviewer, who can dispute it. The facts list names no value to copy. `look` no longer loads PyYAML. A JS constant named like a colour, such as `WHITE`, is no typed colour in a script file (`.js`, `.jsx`, `.ts`, `.tsx` and the module forms). There, a name counts when it is quoted, when it is written in lower case and is no member such as `theme.white`, or when its declaration ends with `;` or is a `[prop:value]` class. A stylesheet and an HTML file still read a name in any case. Five old Complete plans that named the deleted look tests now name the tests that replace them. Non-goals: teaching `look` to read the stylesheet theme or an alpha, and any new rule.

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
- [x] A colour name in script code counts when it is quoted, lower case and no member, or before a `;` or a `[prop:value]` class; an upper-case constant and a member do not; a stylesheet and an HTML file read a name in any case → `tests/test_ui_raw_forms.py::test_a_colour_name_in_script_code_counts_only_as_a_quoted_string`
- [x] `ship` still loads the PyYAML runtime → `tests/test_tool_environment.py::test_ship_loads_the_yaml_runtime_before_it_runs`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`88380e13`) the look, UI-source and audit tests pass (574 cases). The 4 new look tests in `tests/test_look_no_token_verdicts.py` fail there, each on a real assertion (a code verdict that the reviewer should hold, a value in the facts list, token text in the prompt). Run against develop's `ui_raw.py`, 11 of the 29 colour-name rows fail (constants in an options object, a member expression and a typed object); the other 18 guard quoted names, CSS text, a stylesheet and an HTML file. Real project check (counts only): over 4080 web and style files of one real web project, develop reported 2717 colour and size rows; the new reader drops 7 and adds none. The 7 are the reported ones, all a constant named like a colour.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then one commit for the look removal and one for the colour-name fix.

## Risks + recovery

A project with a reviewer Fail on a value that a token list lacks now keeps it as a reviewer item; the whole-project scan of HE-UI-SOURCE still refuses a typed value outside the theme. An upper-case colour name typed as CSS text with no `;` in a script file is not found. A lower-case JS variable named like a colour (`const red = ...; color: red`) is still read as a colour, as before. A quoted name, a lower-case name, a name before a `;` and a `[color:white]` class are found, in any template or string. A bare number in a typed style object is not read, as before; no size rule changes. Recovery: revert the two commits.

## ux_reference

N/A — hook validation logic and tests only; no visible UI.

## Verification

Result: Passed
Evidence: Focused tests pass: all look, UI-source, audit and plan tests (553 cases before the colour-name fix) and the HE-UI-SOURCE, plan and look tests again after it (356 cases). The new look tests fail on `origin/develop` (4 of 7) and the new colour-name rows fail there (8 of 15 at the final form, each on a real assertion). Static gates pass with the exact commands of `hard-eng.gates.json`: format, lint, complexity, annotations, types, dead-code and security (semgrep). `hot-paths` on the touched sources: 0 findings. The five look modules and the item kind text equal `main`. The independent review found a plan reference break and colour-name regressions in earlier heads; each is fixed with a test, and the review of the last code head is recorded in the PR.
E2E: N/A — hook tests run real temporary Git repositories and real file text; no user journey changes.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Escaped bug: the join kept develop's look modules, so a second owner of the token rule came back and a false colour Fail could not be disputed; the gate is the look tests that hold a token list and the colour-name rows → `tests/test_look_no_token_verdicts.py::test_a_gap_and_a_radius_outside_the_token_lists_stay_with_the_reviewer`. Second escaped bug: the colour-name fault passed every gate; the gate is the same raw-form rows, and the colour-name rows fail on develop → `tests/test_ui_raw_forms.py::test_a_colour_name_in_script_code_counts_only_as_a_quoted_string`. Review correction: the first colour-name change used the style-object state, which missed 6 of the 7 real rows, and then dropped three real forms; a check of the real project found it, and the rows now pin each form. Ran too late: none. Single source: HE-UI-SOURCE for every token verdict.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
