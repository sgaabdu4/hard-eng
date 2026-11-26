# Look repairs from develop to main, without the whole-project UI scan

Status: Complete

## Outcome + scope

Installed projects on `main` get the `look` repairs that develop holds: element facts with kind tags, exact keys, code verdicts for measured items, weight and align facts, the fixed gap order, the stale image refusal and the earlier-item lists. New on `main` beyond the measured-fact repairs: the kind-tag, key and stale-image refusals, the count guard of `look_answer.py` (the earlier hotfix left it out), the measured token refusals of `look_records.py` (a corner radius, gap or colour in no `DESIGN.md` token fails `Design system`, `Spacing` or the colour rule in code), the first verdict kept at a head, a Fail item with a leading frame and the `Recheck` line forms of `look_answer.py`, and two reviewer rule sentences: the Alignment line about a field action being an icon inside its field (develop `19a9e291`) and the Design system line that a value in no token becomes a token first (it replaces `A one-off size or radius needs a reason in the plan`, so the text matches the radius refusal). The coordinator can cut either sentence with its test. The judgement recheck of develop is in: a disputed Fail goes to an evidence re-review of the item (`look_dispute.py`), a claim about a keyed element is checked in code in the direction of the claim, each corner of a control or chip is recorded, and `look` loads the YAML runtime before it reads any token. Non-goals: the whole-project HE-UI-SOURCE pass and its modules, the strict `AGENTS.md` changes, the request hold and everything that depends on it (route init script, session cap, idle limit), the wrapped-label rule, the masked-document check, and every other develop change. The judgement recheck of develop is in, see below.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-25.

## Repository context

Owners: `.hooks/look.py` (prompt, run flow), `.hooks/look_answer.py` (item parse, refusals, new on `main`), `.hooks/look_reviewer.py` (reviewer sessions, moved out of `look.py`, new on `main`), `.hooks/look_dispute.py` (evidence re-review of a disputed item, new on `main`), `.hooks/look_facts.py` (facts text, tokens, keys, verdicts, new on `main`), `.hooks/look_records.py` (earlier items, code decisions), `.hooks/ui_measure.py` (measure script, kind table, record), `.hooks/browser.py` (stores the measured values), `.hooks/ui_proof.py` (`measure_found`), `.hooks/ui_tokens.py` (new on `main`: only the colour reader that `look_facts` imports).
Evidence: `origin/main` is `afebcb46`. `origin/develop` is `b1f87886`. The judgement recheck commits `3631eb9a..5af17593` are picked with `cherry-pick -x`, or, where a commit also touches a develop plan or the ship entry `deliver.py`, by their other files only, with a `Look part only` line in the message. The first-party list of `pyproject.toml` conflicted in `3631eb9a` and `920e9ce8`; each was resolved by keeping this branch's list and adding the new module. Per-commit cherry-pick of the first develop commits conflicts at the second commit, because `main` holds hand ports of older develop commits (the earlier look hotfix). So the files come from `git diff origin/main origin/develop` limited to the look paths, and each leave-out is cut by hand.
Same cause: `main`'s `look` lets a reviewer state a size, colour or gap by eye, and installed projects get reviewer Fails that the measure disproves. Develop fixed it in the commits below. The four look modules and seven look test files equal develop, so every develop commit that touched them is in, and the two earlier look hotfixes already hold some of them by hand. Whole, because every file they touched now equals develop (81): 387083e8 0463453b f8d50eae 501816ce d3339394 0d6f6c66 41c5e56c 218bb1e1 94559665 ad1c71f7 5c14f26f be2019f6 08bad7ae 35441eff 9eff70c7 0f9c6c17 aaa2ac9d b627c01a 60575113 e60f77d3 03873e35 e52c6c5f 426359af df11fbd9 7b28d378 229a60b4 0c360fdf a1a21464 2211f987 83b8cb54 185da681 c6848f03 a21c9009 7e9e7e10 b6b17fb4 720734c8 9c930721 2cdef0c9 681c8a3e c49c2978 7838ee34 93694875 5d298b45 b1ad0166 8ab0cfbf 7575a610 ed910a75 facb87e5 709c6962 dc1d1cbc 63a5241a 37bafc3f bab9a6b5 e67736cf d086fbd1 e0e376e5 7e35d3e1 6eea8e6a b66ed5a8 da7599e3 acb13e9f 8e3ef5b7 9f76d224 1bb66522 1099276e c05e77d5 ce0c91a8 fab9d956 e3ff7a54 98370203 1afed6b1 ead821db 512521f1 a036a382 23fffdd3 67717bab 4bb35ce9 de06065b 4dafee84 c39b1f8d 01aac516. Look part only (30): 0daf0fac 4fa434e9 558e93a4 42bbac78 1aeced72 eb78609f 86ccddb6 0815bfe6 30bcfa5f 4443618e 8250075c 64cc28dc c5aec31b 8ef93c7a de4b3b60 8567c525 26635b08 36b4da70 16f64a21 e330f34d f10a5c0b 1469f513 b7c74f63 4142757b beaaa2b7 30462a4d c6179985 3df90a12 92709cf4 462fc8fd. The earlier fixes helped on develop only; the `Fix:` rule, the carry and the proof kinds were in the earlier hotfixes and stay.
Recheck pick (19 develop commits): whole `3631eb9a` `f6937d5a` `920e9ce8` `7c064751` `9eaa2222` `10b6f411` `13bd07f0` `f344831f` `3eaffced` `5af17593`; look part only `a69097cd` `80829374` `17f085b7` `5389930e` (left out: the develop plan of the recheck, and the `deliver.py` hunk of `17f085b7`, which a separate commit supplies); not taken, plan only: `5c515d97` `8f235ec1` `b9d47bdf` `bc61eddb` `589f8663` `b1f87886`. `look.py`, `look_answer.py`, `look_facts.py`, `look_records.py`, `look_dispute.py`, `look_reviewer.py` and every look test file equal develop. `deliver.py` is new on `main` and holds `main`'s own command dispatch moved out of `gate_runner.py` (which was at 999 lines), with the YAML runtime load in the ship branch, because the ship look proof reads `DESIGN.md` tokens and `tests/test_look_runtime.py` imports `deliver`. It differs from develop's `deliver.py` by the `ui-library` branch, which belongs to the whole-project scan.
Left out of mixed commits: `0815bfe6`, `4fa434e9` and `c6179985` (request hold, fetch waves, route init script), `4443618e` (wrapped-label rule), `4142757b` (masked document check), `8567c525` (session cap), and the `ui_tokens` parts for the whole scan. `ui_tokens.py` here holds only `colours_in`, `half_up`, `FRONT_MATTER` and the helpers they call.
Single source: the item kinds stay one table, `ITEM_KINDS` in `ui_measure.py`. Facts are written by the measure script once and read by `look_facts.py`. Searched `.hooks` and `tests` for other readers of `measured`: `browser.py` (writes), `look_records.py` (reads). The judgement recheck PR on develop will change `radiusOf` in `ui_measure.py` and `align_facts` in `look_facts.py`; both stay plain develop code so those commits pick cleanly.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the coordinator's hotfix brief of 2026-11-25; the PR is opened and not merged.

Review declined: `kept_verdict` locks `look` to the first verdict at a head and ignores a later capture's non-visual findings :: this is the merged develop behaviour (`681c8a3e`, `Keep the first look verdict at a head`), ported unchanged; the ship and local proof still refuse an After capture with findings, so a stale clean verdict cannot pass a head with findings; a change to the lock is a develop change
Review declined: a semicolon in intro prose before a passing measured item leaves a frameless prose part and keeps the Fail :: that prose is a claim of the reviewer with no item for code to measure, so it stays with the reviewer, who can end it with a recheck line; the same finding was declined on develop in `features/look-element-facts/PLAN.md`

## Acceptance + steps

- [x] The prompt names each element with its measured facts and says what each check covered → `tests/test_look_facts.py::test_the_prompt_names_each_element_with_its_measured_facts`, `tests/test_look_facts.py::test_the_prompt_says_what_each_check_covered`
- [x] A Fail item with a number or colour and no measured tag is refused, and code decides each measured kind from its exact key → `tests/test_look_facts.py::test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused`, `tests/test_look_facts.py::test_code_decides_each_measured_kind`, `tests/test_look_keys.py::test_a_measured_item_is_decided_from_its_exact_key`, `tests/test_look_keys.py::test_a_measured_item_with_no_valid_key_is_refused_by_form`
- [x] Code decides font weight and text alignment from the measured facts → `tests/test_look_keys.py::test_code_decides_font_weight_against_its_neighbours`, `tests/test_look_keys.py::test_code_decides_text_alignment`
- [x] The record holds each element with its facts and every rounded element's radius, and code decides each kind the same way in five real captures → `tests/test_ui_audit_guards.py::test_the_record_holds_each_element_with_its_facts`, `tests/test_ui_audit_guards.py::test_the_record_holds_the_corner_radius_of_every_rounded_element`, `tests/test_ui_audit_guards.py::test_code_decides_each_kind_the_same_way_in_five_real_captures`
- [x] The gap between inline neighbours follows their order on the line, and wrapped left text in a centred box is not centred → `tests/test_ui_gap_and_init_script.py::test_the_gap_between_inline_neighbours_follows_their_order_on_the_line`, `tests/test_ui_gap_and_init_script.py::test_wrapped_left_aligned_text_in_a_centred_box_is_not_centred`
- [x] A stale image copy is refused and the newer capture is named → `tests/test_look_stale.py::test_a_stale_copy_is_refused_and_the_newer_capture_is_named`
- [x] An earlier measured item is decided by code before the prompt, and an earlier item of a covered image is not listed → `tests/test_look_facts.py::test_an_earlier_measured_item_is_decided_by_code_before_the_prompt`, `tests/test_look_facts.py::test_an_earlier_item_of_an_image_that_a_later_clean_record_covers_is_not_listed`
- [x] The reviewer answer shapes of the fixture files are read as their file names say → `tests/test_look_answer.py::test_a_real_reviewer_answer_shape_is_read_as_its_file_name_says`
- [x] The Alignment rule line says a field action is an icon inside its field → `tests/test_look.py::test_the_prompt_tells_the_reviewer_a_field_action_is_an_icon_inside_its_field`
- [x] `capture` keeps working with the new measure reply → `tests/test_browser.py::test_capture_keeps_no_image_when_the_frame_check_fails`
- [x] A disputed Fail goes to an evidence re-review, a dispute that cites nothing real is refused, and a clean record that rests on a dispute carries only while the cited bytes hold → `tests/test_look_dispute.py::test_a_scripted_stands_answer_keeps_the_item_and_records_the_dispute`, `tests/test_look_dispute.py::test_a_dispute_that_cites_nothing_real_is_refused`, `tests/test_look_dispute.py::test_a_clean_record_that_rests_on_a_dispute_carries_only_while_the_cited_bytes_hold`
- [x] A claim about a keyed element is checked in code in the direction of the claim, and each corner of a control or chip is recorded → `tests/test_look_claims.py::test_a_centred_claim_is_checked_in_its_own_direction`, `tests/test_look_claims.py::test_a_touch_claim_is_checked_against_the_gap_of_its_pair`, `tests/test_ui_corner_facts.py::test_square_chips_are_recorded_and_decided_from_their_own_corners`
- [x] `look` loads the YAML runtime before it reads a token, and refuses clearly when it cannot → `tests/test_look_runtime.py::test_look_loads_the_yaml_runtime_before_it_reads_anything`, `tests/test_look_runtime.py::test_an_unreadable_runtime_is_a_clear_refusal_not_a_silent_fallback`
- [x] Proof on separate real projects → N/A — no test can run a separate project from this repository; the coordinator proves it after the merge

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

1. `look.py` is 817 lines now, since the reviewer sessions moved to `look_reviewer.py`, as on develop.
2. The measure script returns `{found, measured}` and the capture stores `measured`. Old records without `measured` still load: `look` leaves their measured items to the reviewer.
3. Develop keeps the request hold, so records written on develop and on `main` differ. A record from `main` never carries to develop and the next `look` reviews again. That is safe.
4. The two `ux.md` sentences are new reviewer rules that the brief did not list; each can be cut on its own.
5. `ui_proof` on `main` still calls `design_hash(root)` for the disk file where develop passes the head. They differ only when `DESIGN.md` changes after the head.
6. Recovery: revert the merge on `main` with a new hotfix PR.
Not checked: any installed project before the PR is merged.

## ux_reference

N/A — hook code, tests and one skill sentence; no visible UI.

## Verification

Result: Passed
Evidence: Focused run after the port: 426 tests passed in 409 s (look files, browser, audit guards, gap test, ui quality, local proof, capture match). The Ready check ran the full suite: 7938 tests passed in 599 s and every gate passed except `declarations`, which named `look_answer`, `look_facts` and `ui_tokens` as missing first-party modules; they joined the first-party list and `deptry` then reported no issue. The plans of the earlier look hotfixes named tests that moved to `tests/test_look_answer.py`; their acceptance lines now name the new place. `git diff origin/develop HEAD` over `look.py`, `look_answer.py`, `look_facts.py`, `look_records.py` and the seven look test files is empty. The diff of `ui_measure.py` against develop holds only the request hold, the fetch wave source and the wrapped-label rule. A real `browser capture` of a one-page site wrote records with `measured` (texts, gaps, sizes, radii, root_px) and no findings at three widths.
E2E: N/A — hook code with no visible UI; the measure runs in real browsers in `tests/test_ui_audit_guards.py` and `tests/test_ui_gap_and_init_script.py`
Real service: Passed — Claude reviewer CLI: one real `look` run on the three real captures returned a readable answer with no form refusal; the one Fail line carried a kind tag (`[judgement]`) and a `Fix:`; the measured rules came from the browser record (`measured: 0 findings at 390, 768 and 1280`)
Retro: (1) Fault on `main`: a reviewer states a size, colour or gap by eye and the measure disproves it, and `main` never got develop's repairs because develop also holds the whole-project scan → `tests/test_look_facts.py::test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused`, `tests/test_look_facts.py::test_code_decides_each_measured_kind`. (2) A per-commit pick conflicted at the second commit, since `main` holds hand ports of older develop commits, so the port took the look files whole and cut the leave-outs by hand → the `git diff origin/develop HEAD` check of the look files in Verification above. (3) The `declarations` gate caught three modules missing from the first-party list, fixed at once → the `declarations` gate of `hard-eng.gates.json`, which already runs on each change.
Not checked: a code verdict on a real reviewer answer that holds a measured item (the one real answer held only a judgement item); the request hold (left out on purpose; a real `open --init-script` followed by a later step kept the script's value on this branch, so the route init repair needs no port); `design_hash(root, head)` in `ui_proof` (left as `main`); any installed project before the merge.

Delivery target: PR
Delivery: Pending — the PR to `main` passes `hard-eng`.
