# Look: code decides each look Fail item it can measure

Status: Complete

## Outcome + scope

`look` sends the reviewer the measured facts of each element by name, with what each check covered. Each Fail item names its image, element and kind. Code decides each measured item whose element it finds. Only judgement items go on the recheck list. `look` ends a findings run with one line about the rules, and names a changed input before it reviews all images again. Non-goals: a union of three reviewers (tried, left out, see Verification), blocking only on touched parts, non-blocking advice, answered or declined lines, raised limits, skip lists, new measures (weight, line counts, position).

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-25 and its two added lines.

## Repository context

Owners: `ui_measure.py` (measure script, record, fact text, kind table), `look_records.py` (tokens, code verdicts, earlier items), `look_answer.py` (item parse, refusals), `look.py` (prompt, run flow).
Same cause: a reviewer states a size or colour by eye and is wrong. `look_px.py` tried to refuse such a line and matched 0 of 9 stored Fail lines. The kind tag replaces it, so `look_px.py` and `tests/test_look_px.py` end here. Its test protected one thing: a hedged px size that the record does not hold is refused. The replacement proof is `test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused` (the same hedged line is refused) and the code verdict tests.
Single source: the tap and text floors stay in `LIMITS`; the page script writes `under` and `exempt` from the same rule that makes the findings, and Python reads them. Token lengths and colours are read from `DESIGN.md` by one reader in `look_records.py` that also serves the radius check. The item kinds are one table, `ITEM_KINDS` in `ui_measure.py`, which the prompt, the refusal and the verdict read. Searched `.hooks` and `tests` for other readers of `measured`: `browser.py` (only writes), `ui_proof.py` (findings only), `test_ui_audit_guards.py` (changed in the same commit as the record).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; client look reviews do not converge.
Decisions made here, each with a reason:
1. An item with no tag and no number is a judgement item. The brief refuses only an item that states a number or a hex colour without a measured tag. A line that states a number outside a tagged item is also refused, because prose is where the false sizes came from.
2. An earlier measured item whose element code cannot find now stays on the recheck list, as the reviewer's. Code decides only what it finds, so no rule gets softer. This is the reading of brief items 3 and 4 together. Maintainer: tell me if an earlier item whose element is gone should drop instead.
3. The kinds are `size`, `colour`, `gap`, `radius`, `tap` and `judgement`. Weight, line counts and "far from its text" are not owned by code in this change; they stay judgement. The research expected 8 of 19 stable Fails from this change, not 14.
4. A tag states what code checks: `size` is the rendered text size against the floor, `tap` is the control size against its floor, `colour` is text colour and fill against `DESIGN.md` colour tokens, `gap` is a spacing token, `radius` is a rounded token. A placement fault is `judgement`. The prompt says so.
5. A name matches an element only when the item's element text, after the words `button`, `link`, `text`, `label`, `icon`, `badge`, `chip`, `tab`, `field`, `input`, `heading` and `control` are removed, equals the record name (3 letters or more), and every record entry of that name gives the same verdict. Any other case is "not found" and the item stays with the reviewer.

6. The union of three parallel reviewers was built and measured, then left out of this change. Its bar was fewer rounds and fewer tokens to clean and no rise of surviving false Fails. The numbers are under Verification. The maintainer chose to leave it out.
7. `look` keeps one reviewer per run, as before this change.
8. An unknown or missing kind on an item with no number is a judgement item and never refuses a line.
9. Colour tokens come from the DESIGN.md front matter only. A colour in a project token file that DESIGN.md lacks is a project fault that `token_findings` already reports.
10. `agy` is not a reviewer of `look` in this change: `look` has no proof of the images that `agy` opened. Adding it needs its own proof form and is left to a separate change.

## Acceptance + steps

- [ ] The record holds each text element with its name, size, weight and raw colour and fill, each control with its floor and `under`, each gap between named neighbours and each radius, with no cut → `tests/test_ui_audit_guards.py::test_the_record_holds_each_element_with_its_facts`
- [ ] The prompt names each element with its facts and the colour token → `tests/test_look_facts.py::test_the_prompt_names_each_element_with_its_measured_facts`
- [ ] The prompt says what each check covered, for example `tap size checked for all 3 controls: 0 under 44 px` → `tests/test_look_facts.py::test_the_prompt_says_what_each_check_covered`
- [ ] A long list is bounded by one stated byte rule and says how many it left out, in the same order each time → `tests/test_look_facts.py::test_a_long_fact_list_is_cut_by_the_stated_rule_and_counts_what_it_left_out`
- [ ] A Fail item that states a size, a colour or a ratio without a measured tag is refused as not done, an unknown tag with such a number is refused too, and an unknown tag with no number stands as judgement → `tests/test_look_facts.py::test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused`
- [ ] A tagged item, and an untagged item with no number, stand → `tests/test_look_facts.py::test_a_tagged_item_and_an_untagged_item_without_a_number_stand`
- [ ] The prompt names the kinds and what they cover from the one table → `tests/test_look_facts.py::test_the_prompt_lists_the_kinds_from_the_one_table`
- [ ] Code decides each measured kind, with one known fault and one known pass for each → `tests/test_look_facts.py::test_code_decides_each_measured_kind`
- [ ] An ambiguous, short, unknown or unmatched element stays with the reviewer → `tests/test_look_facts.py::test_an_item_that_code_cannot_match_stays_with_the_reviewer`
- [ ] A colour token with alpha matches the raw colour of the element → `tests/test_look_facts.py::test_a_colour_token_with_alpha_matches_the_raw_colour`
- [ ] The other items of a line stay, and a line whose items all pass in code becomes a Pass → `tests/test_look_facts.py::test_the_other_items_of_a_line_stay_and_all_passed_items_make_a_pass`
- [ ] An earlier measured item is decided by code and not listed; an earlier true colour Fail stays a Fail when the reviewer says nothing; an earlier false item never returns → `tests/test_look_facts.py::test_an_earlier_measured_item_is_decided_by_code_before_the_prompt`
- [ ] An earlier measured item that code cannot find stays on the recheck list; judgement items stay there → `tests/test_look_facts.py::test_an_earlier_item_that_code_cannot_find_is_listed_again`
- [ ] A findings run ends with the one line about the rules → `tests/test_look_facts.py::test_a_findings_run_ends_with_the_line_about_the_rules`
- [ ] Code decides each kind of invented fixture the same way in 5 of 5 real browser captures → `tests/test_ui_audit_guards.py::test_code_decides_each_kind_the_same_way_in_five_real_captures`
- [ ] A changed DESIGN.md or plan scope is named before the review → `tests/test_look_facts.py::test_a_changed_input_is_named_before_all_images_are_reviewed_again`
- [ ] Each stored reviewer answer shape is read as its file name says, including the two PR 731 refusals → `tests/test_look_answer.py::test_a_real_reviewer_answer_shape_is_read_as_its_file_name_says`

Steps:

1. Commit this plan.
2. For each of the five build items (facts, tags, code verdicts, recheck list, two added lines): red test, see it fail, build, run the focused tests, commit.
3. Static gates, `check --plan-stage Ready --base origin/develop`, `challenge` to a clean headline at the exact head, `check --plan-stage Complete --base origin/develop` once.
4. Proof: one fixture for each kind in 5 of 5 real captures; 5 look runs on each sealed copy; the earlier list against none on one set; the borderline fixture 5 times.
5. PR to `develop`, `pr-text`, CI, `ship --stage ready`, `ship --stage merge`, `ship --stage delivered`.

## Baseline + execution

Result: Passed
Evidence: 128 focused look tests pass on `origin/develop` `f7f5e167` (`tests/test_look.py`, `test_look_answer.py`, `test_look_carry.py`, `test_look_proof_kinds.py`, `test_look_px.py`).
Execution: One builder in `fix/look-element-facts`. A fresh reviewer runs `challenge` on the candidate head.

## Risks + recovery

1. Every image key changes once, because the facts text in the prompt changes. A clean record of an old head does not carry; the next run reviews each image again. An old-format browser record has no element facts, so code decides nothing for it and the reviewer decides as before.
2. A wrong match would let code overrule the reviewer with a false Pass. The match is strict (decision 5) and each near miss has a test.
3. A reviewer that tags a size claim with the wrong kind gets a code Pass on the wrong fact. The prompt states what each tag checks; a placement fault under `size` finds the element at its floor and passes it.
4. One reviewer finds a given fault in about 0.40 to 0.55 of runs on real sets, so a clean run can still miss a fault. This change does not raise that rate. The union tried to (decision 6) and did not pay.
5. Facts can reach about 6 KB per image.
6. Recovery: revert the merge on `develop` with a new PR.
Not checked: the union of three reviewers, which was built and left out (four times the tokens per run, no recall gain on the fixtures, more Fails on the fixed page); the real sealed sets, which need captures in the new measure format; agy as a reviewer; the `building-flutter-apps` copy of the hooks; any installed project.
Review declined: remove `verifier-tests.patch` as dead code :: the maintainer asked to keep it, with the 30-run numbers, as the start of the next attempt at a union.
Review declined: a number or hex colour in a second item that shares the frame prefix of a measured item bypasses the refusal :: the line with a second tag stays with the reviewer and code decides none of it, and a refusal there would also refuse the real shape `image-1.png: Save [size], Hint 10 px [size]`; the refusal covers the one-item form that the prompt asks for.
Review declined: a semicolon in the prose before a measured item leaves a frame-less prose part on a Fail line :: that prose is a claim of the reviewer with no item for code to measure, so it stays with the reviewer (decisions 1 and 2) and the reviewer can end it with a recheck line.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Passed
Evidence: `check --plan-stage Ready --base origin/develop` passed (8101 tests, the static gates and the semgrep rules) before the repairs; the focused look tests then passed after each repair and after the rebase on `develop`. Each repair had a test that fails without it. The independent review by another agent ran 5 rounds: rounds 1 to 4 found real faults in the carried tokens, lists of items, old records, gap overlap, order numbers, partial carries and held images (each repaired with a red test) and 3 findings that the plan declines with a reason; round 5 ended clean. CI is the full test proof.
E2E: N/A — hook code with no app journey; the real browser capture and the fixture runs are the Real service proof.
Real service: Passed — the Claude reviewer CLI and the real browser capture, on invented fixtures only: (1) Real browser capture: one invented fixture for each kind (size, colour, gap, radius, tap), code gave the same verdict in 5 of 5 captures for each. (2) Real Claude reviewer, this change, one reviewer, 3 invented pages (faulty, fixed, v1), 5 runs each: 15 of 15 ended `findings`, 0 of 15 form refusals; on the faulty page both planted faults were found in 5 of 5 runs, and code gave the same Fails in every run of a page (5 of 5 faulty, 5 of 5 v1); 25k to 44k tokens per run. (3) Union of three reviewers, same pages, 15 runs: 15 of 15 counted 3 of 3, 0 form refusals, 78k to 124k tokens per run (about 4 times), both planted faults found 5 of 5 as with one reviewer, no recall gain; neither mode reached a clean run on the fixed page (it keeps an enabled Approve on an incomplete order, found 5 of 5 by each), so rounds to clean could not be measured; the union raised Fails per run on the fixed page (2 to 4 against 1 to 3) and repeated one fault as several items. The union was left out. The tests of its verify step are kept in `features/look-element-facts/verifier-tests.patch` (they apply to a union build, not to this branch); the verify step was never built. Not checked: the real sealed sets (they need captures in the new measure format), agy, the borderline fixture of the earlier PR, the earlier list against none.
Retro: Look reviewers stated sizes and colours by eye and were wrong, and a guard that refused such lines matched 0 of 9 stored Fail lines. The record now holds each element with its facts, each Fail item names its image, element and kind, and code decides each tagged item it finds against the floor and the DESIGN.md tokens; the recheck list keeps judgement items. A union of three reviewers cost four times the tokens with no recall gain, so it was left out. Escaped bug: found on the base branch; the red tests of this PR are its repro and the fix is in this PR.

Delivery target: Merge

Delivery: Pending — required remote proof.
