# Repair the faults that the release proof found on develop

Status: Ready

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
1. Review finding 4 (unitless numbers in extra `DESIGN.md` groups count as px) is not changed. A Dart token file holds each length as a bare number (`static const double`), so the real Flutter project that keeps a width in an extra group needs the bare number to match. Removing it turns a passing project into a failing one. The CSS-only false case (a `zIndex` group) stays a stated limit.
2. A measured item must copy one key exactly. A measured item with no valid key is refused by form, so the reviewer is asked again. No loose name match exists, because a wrong match gives a false verdict. This replaces decision 5 of `features/look-element-facts/PLAN.md` (name match with role words dropped), which decided 0 of 15 real items.
3. Weight and text alignment become fact kinds. A record without the new fields gives no fact, so code decides nothing for an old record. A weight item is a claim that the text differs from its neighbours in the same row; an align item is a claim that the text is not centred in its parent. Any other claim about weight or alignment is a judgement item, and the kind table says so.
4. The tap kind already existed and already held the 44 px links of the real record. What the reviewer lacked was a key to name them, and the facts line did not say that a control meets its floor. The line now says `at or over N px`, and the key decides the item. No new tap fact is added.
5. An image with no measured record has no key, so a measured item on it is refused by form and the reviewer tags it as a judgement item. The prompt says so.
6. Review findings 1 and 2 share one cause, so one function (`owned_texts` in `ui_whole.py`) gives every token reader, the library index and the token compare the same files: no tool folder, test or generated file. Comments in a stylesheet define no token.
7. The new tests live in their own files because four test files passed the file length limit.

## Acceptance + steps

- [ ] A DESIGN.md `rounded` or `spacing` token of `0` is a zero length and does not turn off the radius and gap verdicts → `tests/test_look_keys.py::test_a_zero_token_is_a_length_and_keeps_the_other_verdicts`
- [ ] A `--font-size-*`, `--font-weight-*` or `--font-style-*` property is not a font family → `tests/test_ui_token_sources.py::test_a_font_property_that_is_not_a_family_adds_no_family`
- [ ] A comment, a test file and a generated file define no token colour or length → `tests/test_ui_token_sources.py::test_a_comment_a_test_file_and_a_generated_file_define_no_token`
- [ ] The library index and the token compare skip tests, generated files and tool folders → `tests/test_ui_token_sources.py::test_the_library_index_and_the_token_compare_skip_tests_and_generated_files`
- [ ] The gap between inline neighbours follows their order on the line → `tests/test_ui_gap_and_init_script.py::test_the_gap_between_inline_neighbours_follows_their_order_on_the_line`
- [ ] Code decides font weight against its neighbours → `tests/test_look_keys.py::test_code_decides_font_weight_against_its_neighbours`
- [ ] Code decides text alignment from text-align and the box position → `tests/test_look_keys.py::test_code_decides_text_alignment`
- [ ] A control at its floor says so in the facts list, and code decides its tap item → `tests/test_look_keys.py::test_the_tap_fact_of_a_link_at_its_floor_says_so_and_code_decides_it`
- [ ] Code decides weight, alignment and the other kinds the same way in 5 of 5 real captures → `tests/test_ui_audit_guards.py::test_code_decides_each_kind_the_same_way_in_five_real_captures`
- [ ] The facts list shows one key for each measured element, and code decides a measured item only from an exact key → `tests/test_look_keys.py::test_a_measured_item_is_decided_from_its_exact_key`
- [ ] A measured item with no valid key is refused by form → `tests/test_look_keys.py::test_a_measured_item_with_no_valid_key_is_refused_by_form`
- [ ] The real items of the release proof are decided from keys, and their old shape is refused → `tests/test_look_keys.py::test_the_real_items_of_the_release_proof_are_decided_from_keys`
- [ ] The counter item and the centred items are decided by code → `tests/test_look_keys.py::test_the_counter_and_the_centred_items_are_decided_by_code`
- [ ] A route's init script and the hold script both run on every step of a session → `tests/test_ui_gap_and_init_script.py::test_a_capture_keeps_the_route_init_script_beside_the_hold_script`
- [ ] A step that started the page again for its init scripts is refused, and a missing init script file is refused → `tests/test_browser_init_scripts.py::test_a_step_that_started_the_page_again_for_its_init_scripts_is_refused`
- [ ] A stylesheet that mixes `@theme` tokens with other rules gets a line that says why and what passes → `tests/test_ui_token_sources.py::test_a_mixed_stylesheet_gets_a_token_gap_line_that_says_why`

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
3. Recovery: revert the merge on `develop` with a new PR.
Not checked: any installed project.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Pending
Evidence: pending.
E2E: N/A — hook code with no app journey.
Real service: N/A — no outside service; the real browser capture is the proof of the gap fact and the init script.

Delivery target: Merge

Delivery: Pending — required remote proof.
