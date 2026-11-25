# Look repairs from develop to main, without the whole-project UI scan

Status: Ready

## Outcome + scope

Installed projects on `main` get the `look` repairs that develop holds: element facts with kind tags, exact keys, code verdicts for measured items, weight and align facts, the fixed gap order, the stale image refusal and the earlier-item lists. Non-goals: the whole-project HE-UI-SOURCE pass and its modules, the strict `AGENTS.md` changes, the request hold and everything that depends on it (route init script, session cap, idle limit), the wrapped-label rule, the masked-document check, the judgement recheck work, and every other develop change.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-25.

## Repository context

Owners: `.hooks/look.py` (prompt, run flow), `.hooks/look_answer.py` (item parse, refusals, new on `main`), `.hooks/look_facts.py` (facts text, tokens, keys, verdicts, new on `main`), `.hooks/look_records.py` (earlier items, code decisions), `.hooks/ui_measure.py` (measure script, kind table, record), `.hooks/browser.py` (stores the measured values), `.hooks/ui_proof.py` (`measure_found`), `.hooks/ui_tokens.py` (new on `main`: only the colour reader that `look_facts` imports).
Evidence: `origin/main` is `afebcb46`. Per-commit cherry-pick of the develop commits conflicts at the second commit, because `main` holds hand ports of older develop commits (the earlier look hotfix). So the files come from `git diff origin/main origin/develop` limited to the look paths, and each leave-out is cut by hand.
Same cause: `main`'s `look` lets a reviewer state a size, colour or gap by eye, and installed projects get reviewer Fails that the measure disproves. Develop fixed it in these commits, picked by their look part: `e67736cf`, `d086fbd1`, `e0e376e5`, `7e35d3e1`, `6eea8e6a`, `da7599e3`, `b66ed5a8`, `acb13e9f`, `1bb66522`, `1099276e`, `c05e77d5`, `ce0c91a8`, `98370203`, `30462a4d`, `1afed6b1`, `ead821db`, `a036a382`, `23fffdd3`, `4bb35ce9`, `de06065b`, `4dafee84`, `c39b1f8d`, `01aac516`, `dc1d1cbc`, `bab9a6b5`, `5d298b45`, `c49c2978`, `7838ee34`, `0463453b` (measured values part), `8ef93c7a`, `c5aec31b`, `aaa2ac9d`. The earlier fixes helped on develop only. The `Fix:` rule, the carry and the proof kinds were in the earlier look hotfix and stay.
Left out of mixed commits: `0815bfe6`, `4fa434e9` and `c6179985` (request hold, fetch waves, route init script), `4443618e` (wrapped-label rule), `4142757b` (masked document check), `8567c525` (session cap), and the `ui_tokens` parts for the whole scan. `ui_tokens.py` here holds only `colours_in`, `half_up`, `FRONT_MATTER` and the helpers they call.
Single source: the item kinds stay one table, `ITEM_KINDS` in `ui_measure.py`. Facts are written by the measure script once and read by `look_facts.py`. Searched `.hooks` and `tests` for other readers of `measured`: `browser.py` (writes), `look_records.py` (reads). The judgement recheck PR on develop will change `radiusOf` in `ui_measure.py` and `align_facts` in `look_facts.py`; both stay plain develop code so those commits pick cleanly.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the coordinator's hotfix brief of 2026-11-25; the PR is opened and not merged.

## Acceptance + steps

- [ ] The prompt names each element with its measured facts and says what each check covered → `tests/test_look_facts.py::test_the_prompt_names_each_element_with_its_measured_facts`, `tests/test_look_facts.py::test_the_prompt_says_what_each_check_covered`
- [ ] A Fail item with a number or colour and no measured tag is refused, and code decides each measured kind from its exact key → `tests/test_look_facts.py::test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused`, `tests/test_look_facts.py::test_code_decides_each_measured_kind`, `tests/test_look_keys.py::test_a_measured_item_is_decided_from_its_exact_key`, `tests/test_look_keys.py::test_a_measured_item_with_no_valid_key_is_refused_by_form`
- [ ] Code decides font weight and text alignment from the measured facts → `tests/test_look_keys.py::test_code_decides_font_weight_against_its_neighbours`, `tests/test_look_keys.py::test_code_decides_text_alignment`
- [ ] The record holds each element with its facts and every rounded element's radius, and code decides each kind the same way in five real captures → `tests/test_ui_audit_guards.py::test_the_record_holds_each_element_with_its_facts`, `tests/test_ui_audit_guards.py::test_the_record_holds_the_corner_radius_of_every_rounded_element`, `tests/test_ui_audit_guards.py::test_code_decides_each_kind_the_same_way_in_five_real_captures`
- [ ] The gap between inline neighbours follows their order on the line, and wrapped left text in a centred box is not centred → `tests/test_ui_gap_and_init_script.py::test_the_gap_between_inline_neighbours_follows_their_order_on_the_line`, `tests/test_ui_gap_and_init_script.py::test_wrapped_left_aligned_text_in_a_centred_box_is_not_centred`
- [ ] A stale image copy is refused and the newer capture is named → `tests/test_look_stale.py::test_a_stale_copy_is_refused_and_the_newer_capture_is_named`
- [ ] An earlier measured item is decided by code before the prompt, and an earlier item of a covered image is not listed → `tests/test_look_facts.py::test_an_earlier_measured_item_is_decided_by_code_before_the_prompt`, `tests/test_look_facts.py::test_an_earlier_item_of_an_image_that_a_later_clean_record_covers_is_not_listed`
- [ ] The reviewer answer shapes of the fixture files are read as their file names say → `tests/test_look_answer.py::test_a_real_reviewer_answer_shape_is_read_as_its_file_name_says`
- [ ] The Alignment rule line says a field action is an icon inside its field → `tests/test_look.py::test_the_prompt_tells_the_reviewer_a_field_action_is_an_icon_inside_its_field`
- [ ] `capture` keeps working with the new measure reply → `tests/test_browser.py::test_capture_keeps_no_image_when_the_frame_check_fails`
- [ ] Proof on separate real projects → N/A — no test can run a separate project from this repository; the coordinator proves it after the merge

Steps:

1. Commit this plan.
2. Commit the look modules with their tests, then the measure and capture part, each with focused tests.
3. Run the static gates, `challenge` until clean for the exact head, then `check --plan-stage Complete --base origin/main` once.
4. Open the PR to `main`. Do not merge.

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at `afebcb46`, `tests/test_look.py`, `tests/test_look_carry.py`, `tests/test_look_proof_kinds.py`, `tests/test_browser.py`, `tests/test_local_ui_proof.py`, `tests/test_ui_quality.py`, `tests/test_ui_capture_match.py` and `tests/test_ui_audit_guards.py` pass: 253 tests in 311 s.
Execution: One builder in a new worktree off `origin/main`. A fresh reviewer runs `challenge` on the candidate head before the Complete check.

## Risks + recovery

1. `look.py` is exactly at the 1000 line limit, as on develop. The judgement recheck commits that join later must keep it there or move code out first.
2. The measure script returns `{found, measured}` and the capture stores `measured`. Old records without `measured` still load: `look` leaves their measured items to the reviewer.
3. Develop keeps the request hold, so records written on develop and on `main` differ. A record from `main` never carries to develop and the next `look` reviews again. That is safe.
4. `ui_proof` on `main` still calls `design_hash(root)` for the disk file where develop passes the head. They differ only when `DESIGN.md` changes after the head.
5. Recovery: revert the merge on `main` with a new hotfix PR.
Not checked: any installed project before the PR is merged.

## ux_reference

N/A — hook code, tests and one skill sentence; no visible UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — hook code with no visible UI; the measure is proved by real browser captures in the tests above
Real service: N/A — the reviewer CLIs run behind fakes in the tests, and the coordinator runs the real reviewers after the merge
Retro: Pending

Delivery target: PR
Delivery: Pending — the PR to `main` passes `hard-eng`.
