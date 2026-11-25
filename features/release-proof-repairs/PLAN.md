# Repair the faults that the release proof found on develop

Status: Complete

## Outcome + scope

The release proof of develop found these faults. Each gets a failing test first and a fix at its cause: the facts list shows an exact key for each measured element and `look` decides a measured item only from a key, three fact kinds are missing (font weight, text alignment, link tap size), a gap fact skips a neighbour, a project's own init script is dropped when Hard Eng holds requests, the token-gap line reads as if tokens are missing, and four of the five review findings. Non-goals: the no-fixed-request-delay refusal, a loose name match, a new rule, and any change outside these faults.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-25 and the release proof report.

## Repository context

Owners: `look_facts.py` (facts, kinds, verdict), `look_records.py` (item decision), `look_answer.py` (item form and refusal), `ui_measure.py` (measure script and kind table), `browser.py` (capture), `ui_tokens.py`, `ui_whole.py` and `ui_library.py` (UI source rules), `ui_proof.py` or its owner of the token-gap text.
Same cause: a reviewer writes numbers into an element name, so a name match decided 0 of 15 items. An exact key removes the match.
Single source: the facts list is built once by `look_facts.py`; the key is made there and read there. The kind table stays `ITEM_KINDS`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the coordinator's brief of 2026-11-25 names each fault; standing rule: ask the advisor, not the user.
Decisions made here, each with a reason:
1. Review finding 4 (unitless numbers in extra `DESIGN.md` groups count as px) is fixed in a narrow way. A Dart token file holds each length as a bare number (`static const double`), so a project that keeps a width in an extra group needs the bare number to match its token. Removing the numbers (the review's correction) turns that passing project into a failing one. A bare number now matches a token length that has no unit in its token file (a Dart double) and is never reported as missing from the token files, so a `zIndex` or an opacity group adds no finding. A token length written with a unit is never excused by a bare number. Limit: a Dart double that equals a bare number of another group is excused too. A token length that `DESIGN.md` lacks is still refused. No decision on `develop` settles this finding.
2. A measured item must copy one key exactly. A measured item with no valid key is refused by form, so the reviewer is asked again. No loose name match exists, because a wrong match gives a false verdict. This replaces decision 5 of `features/look-element-facts/PLAN.md` (name match with role words dropped), which decided 0 of 15 real items.
3. Weight and text alignment become fact kinds. A record without the new fields gives no fact, so code decides nothing for an old record. A weight item is a claim that the text differs from its neighbours in the same row; an align item is a claim that the text is not centred in its parent. Any other claim about weight or alignment is a judgement item, and the kind table says so.
4. The tap kind already existed and already held the 44 px links of the real record. What the reviewer lacked was a key to name them, and the facts line did not say that a control meets its floor. The line now says `at or over N px`, and the key decides the item. No new tap fact is added.
5. A fact that code cannot decide (no token, no neighbour, a repeated name) has no key, so an item on it is refused by form and is tagged as a judgement item. An image with no measured record has no key, so a measured item on it is refused by form and the reviewer tags it as a judgement item. The prompt says so.
6. Review findings 1 and 2 share one cause, so one function (`owned_texts` in `ui_whole.py`) gives every token reader, the library index and the token compare the same files: no tool folder, test or generated file. Comments in a stylesheet define no token.
7. The new tests live in their own files because four test files passed the file length limit.

## Acceptance + steps

- [x] A DESIGN.md `rounded` or `spacing` token of `0` is a zero length and does not turn off the radius and gap verdicts → `tests/test_look_keys.py::test_a_zero_token_is_a_length_and_keeps_the_other_verdicts`
- [x] A `--font-size-*`, `--font-weight-*` or `--font-style-*` property is not a font family → `tests/test_ui_token_sources.py::test_a_font_property_that_is_not_a_family_adds_no_family`
- [x] A comment, a test file and a generated file define no token colour or length → `tests/test_ui_token_sources.py::test_a_comment_a_test_file_and_a_generated_file_define_no_token`
- [x] The library index and the token compare skip tests, generated files and tool folders → `tests/test_ui_token_sources.py::test_the_library_index_and_the_token_compare_skip_tests_and_generated_files`
- [x] The gap between inline neighbours follows their order on the line → `tests/test_ui_gap_and_init_script.py::test_the_gap_between_inline_neighbours_follows_their_order_on_the_line`
- [x] Code decides font weight against its neighbours → `tests/test_look_keys.py::test_code_decides_font_weight_against_its_neighbours`
- [x] Code decides text alignment from text-align and the box position → `tests/test_look_keys.py::test_code_decides_text_alignment`
- [x] A control at its floor says so in the facts list, and code decides its tap item → `tests/test_look_keys.py::test_the_tap_fact_of_a_link_at_its_floor_says_so_and_code_decides_it`
- [x] Code decides weight, alignment and the other kinds the same way in 5 of 5 real captures → `tests/test_ui_audit_guards.py::test_code_decides_each_kind_the_same_way_in_five_real_captures`
- [x] The facts list shows one key for each measured element, and code decides a measured item only from an exact key → `tests/test_look_keys.py::test_a_measured_item_is_decided_from_its_exact_key`
- [x] A measured item with no valid key is refused by form → `tests/test_look_keys.py::test_a_measured_item_with_no_valid_key_is_refused_by_form`
- [x] The real items of the release proof are decided from keys, and their old shape is refused → `tests/test_look_keys.py::test_the_real_items_of_the_release_proof_are_decided_from_keys`
- [x] The counter item and the centred items are decided by code → `tests/test_look_keys.py::test_the_counter_and_the_centred_items_are_decided_by_code`
- [x] A route's init script and the hold script both run on every step of a session → `tests/test_ui_gap_and_init_script.py::test_a_capture_keeps_the_route_init_script_beside_the_hold_script`
- [x] A step that started the page again for its init scripts is refused, and a missing init script file is refused → `tests/test_browser_init_scripts.py::test_a_step_that_started_the_page_again_for_its_init_scripts_is_refused`
- [x] A bare number in an extra group matches a token length and is never reported missing → `tests/test_ui_token_sources.py::test_a_bare_number_in_an_extra_group_matches_a_token_length_but_is_never_missing`
- [x] A session that the tool no longer lists loses its saved init scripts, and a session opened outside the command still reaches the request delay refusal → `tests/test_browser_init_scripts.py::test_a_session_that_the_tool_no_longer_lists_loses_its_saved_init_scripts`
- [x] A stylesheet that mixes `@theme` tokens with other rules gets a line that says why and what passes → `tests/test_ui_token_sources.py::test_a_mixed_stylesheet_gets_a_token_gap_line_that_says_why`
- [x] A centred line with an inline link is centred, whatever the number of text fragments on the line → `tests/test_ui_gap_and_init_script.py::test_a_centred_line_with_an_inline_link_is_centred`
- [x] A label repeated in two rows with one style gets no weight verdict → `tests/test_ui_gap_and_init_script.py::test_a_label_repeated_in_two_rows_with_one_style_gets_no_weight_verdict`
- [x] A key whose facts disagree has no key, and its item is refused by form → `tests/test_look_keys.py::test_a_key_whose_facts_disagree_has_no_key_and_its_item_is_refused`
- [x] A listed fact that code cannot decide says it has no key, so a reviewer does not copy it into a measured item → `tests/test_look_keys.py::test_a_listed_fact_that_code_cannot_decide_says_it_has_no_key`

Steps:

1. Commit this plan.
2. For each fault: red test, see it fail, fix, run the focused tests, commit.
3. Static gates, `challenge` to a clean headline at the exact head, `check --plan-stage Complete --base origin/develop` once.
4. Real browser proof for the gap fact and the init script; PR to `develop`.

## Baseline + execution

Result: Passed
Evidence: the full Complete gate passed on `origin/develop` `e3ff7a54` (release proof, step 2).
Execution: One builder in `fix/release-proof-repairs`.

## Risks + recovery

1. A key makes the facts text longer, so every look image key changes once and an old clean record does not carry.
2. A reviewer that does not copy a key gets a form refusal and one more round; the refusal says to copy a key or tag the item as a judgement.
3. A `UI-LIBRARY.md` row that came from a test or generated file in the library folder now fails as a stale row until `ui-library --write` runs; `ui-library --write` reads the same filter (`owned_texts`) and is covered by `tests/test_ui_token_sources.py::test_the_library_index_and_the_token_compare_skip_tests_and_generated_files` only through the check, so its output is not tested on its own.
4. An `[align]` item reads as a claim that the text is not centred. A reviewer who tags a claim that text is centred but should be left-aligned gets a code Pass. The prompt says what the kind checks. The real lines of the release proof hold both directions.
5. A browser step that adds `--init-script` to a session that is already open makes the tool start the page again and lose its viewport; Hard Eng keeps the script for every later step, and the tool prints its own warning on that step.
6. Recovery: revert the merge on `develop` with a new PR.
Not checked: any installed project.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Passed
Evidence: Each fault has a test that failed first on `develop` `e3ff7a54` and passes now: the zero token (`length_scale` returned None), the font properties (five values read as families), the comment, test and generated files (a palette class passed), the gap order (19 px for a 6 px gap), the keys (the 15 real items decided 0 of 15 before), the init script (`undefined/false` for both scripts after a second step) and the token gap line. `check --static` and `check --quick` with `--plan-stage Ready` passed; `hot-paths` on the touched files gave 0 findings. Real tool, 5 inputs through `browser` (a flag only, an environment value only, both, none, the same file twice): 5 of 5 ran the expected scripts and the request hold after a later step. Real records, the 15 tagged items of the release proof mapped to keys by hand and run against the 3 real records of that run, with stand-in tokens: 15 of 15 have a key and 15 of 15 are decided by code. A session opened outside the command still ends with the request delay refusal (checked with the real tool). The five review findings: 1 and 2 fixed (comments, scss line comments, test, generated and tool files, theme files outside `ui_paths`, tailwind config in a test folder); 3 and 5 fixed; 4 fixed in a narrow way (decision 1).
E2E: N/A — hook code with no app journey; the real browser capture is the proof of the gap fact, the kinds and the init script.
Real service: Passed — three real `look` runs with no `--host` flag (Codex was at its usage limit, so `look` used the Claude reviewer by itself), on three captures (390, 768, 1280 px) of an invented order page. Run 1 looked at a wrong page (an old scratch server answered with a 404 page), so it proves nothing. Run 2 ended `not done`: the reviewer copied the listed gap fact `Place order to Cancel` into a `[gap]` item, and that fact has no key because the invented DESIGN.md holds no spacing tokens; the form refusal worked, and the run showed that a listed line without a key looked like a key. That is fixed (a listed fact without a key now says `no key: judgement`) and covered by `tests/test_look_keys.py::test_a_listed_fact_that_code_cannot_decide_says_it_has_no_key`. Run 3, on the final code, ended `findings` (the review outcome, not a pass): 0 form refusals; the reviewer copied the keys `Place order` and `Cancel` into 6 `[tap]` items and code decided all 6 (control 96x32 and 68x32 px, under the 44 px floor); every other item was a `[judgement]` item. The real browser tool ran in the tests and in the five-input check.
Retro: A look reviewer wrote numbers into element names, so a name match decided 0 of 15 tagged items; an exact key replaces the match. A measure sorted neighbours by top edge, so a bolder digit moved last and a gap read 19 px for 6 px; the row order now comes first. Hard Eng set one init script file for every step, so the tool started the page again and dropped the route's own script; the session now keeps both. Prevention: `tests/test_look_keys.py::test_a_measured_item_is_decided_from_its_exact_key`, `tests/test_ui_gap_and_init_script.py::test_the_gap_between_inline_neighbours_follows_their_order_on_the_line` and `tests/test_ui_gap_and_init_script.py::test_a_capture_keeps_the_route_init_script_beside_the_hold_script`. Escaped bug: found on the base branch by the release proof; the gate that should have caught each was the tests gate, and each red test of this PR fails on `develop` `e3ff7a54`. A new `release_canary.py` flow check was read: `install_new` runs no look, browser or UI path, so no new-project flow reaches a new refusal.
Not checked: more than one live `look` run (the keys of a long fact list, cut at 1500 bytes, were not exercised live); the real DESIGN.md of the release proof run (the replay used stand-in tokens); the tenants-page footer links (that record holds no measured values); any installed project.

Delivery target: Merge

Delivery: Pending — required remote proof.
