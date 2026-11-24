# Look-only hotfix from develop to main

Status: Ready

## Outcome + scope

Installed projects on `main` can pass `look`. The reviewer reads three rule-line forms, every Fail line names a fix, a clean verdict carries per image set, the reviewer judges only the rules with the `judgement` kind, a standalone link gets the tap-size check, and a repoint of an old Complete plan's targets keeps that plan's old rules. Non-goals: any refusal that `main` does not have today except the tap-size check, new measure rules or measured values, the px guard, the session refusal, the whole-project UI scan, repoint part 1, the browser session cap and every other develop change.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's hotfix brief of 2026-11-24.

## Repository context

Owners: `.hooks/look.py` (prompt, `clean_line`, `judge`, `review`, `look_command`); `.hooks/look_records.py` (new on `main`: `STORE`, `image_keys`, `covering_record`, `combined`, `earlier_fixes`, `record_files`, `records_for`, and the owner-check lines of the proof kinds); `.hooks/ui_measure.py` (`PROOF_KINDS`, the tap-size script); `.hooks/ui_proof.py` (`browser_record_files`, `look_problem`, `measure_verdict`, `_capture_stems`); `.hooks/local_ui_proof.py` (`_local_look_problem`); `.hooks/plans.py` (`split_rule_line`, `rule_lines`, `line_references`); `.hooks/plan_tests.py` and `.hooks/change_size.py` (`verified_test_ref_repair`); `.hooks/commit_attribution.py` (new).
Evidence: `origin/main` is `009927fb`, the merge base of `main` and `develop`. `develop` is at `0f54046f` (PR 721), with PR 713, 715, 720 and 721 merged. Each kept change is a port by hand from the merged commits, because a trial merge of each commit onto `main` conflicts.

The merged commits that this hotfix ports, and what it leaves out of each:

1. Attribution move, `0ffdffc4` (the move only): `main`'s `plans.py` is 998 lines and `line_references` adds lines, so the file passes 1000 lines (HE-FILE-LENGTH). The move to `.hooks/commit_attribution.py` is the "develop baseline repair that `main` needs to pass its gates". Leave out the other part of `0ffdffc4` (the open-plan message).
2. Rule-line forms, `03873e35` + tests `e60f77d3`, `e52c6c5f`: in `look.py` the prompt form, `PLAIN_VERDICT` and the `clean_line` body.
3. `Fix:` rule, `df11fbd9` + tests `426359af`, `7b28d378`: the prompt sentence, `FIX_PART` and the unfixed check. On develop the check sits in `rule_refusal`, which also holds the count guard and the px guard. `main` has no `rule_refusal`, so the hotfix puts the unfixed check in `judge` with develop's message. Leave out the count guard, `nothing_removed` and `look_px`.
4. Carry, `be2019f6`, `94559665`, `218bb1e1` (carry part only), `ad1c71f7`, `60575113` and the `look --all` part of `9eff70c7`: all of `look_records.py`, the carry parts of `look.py`, `record_files` in the local proof and `records_for` in the ship proof. Leave out `MEASURED_SECTION`, `recorded_measured`, `recorded_values`, the `values` keyword, the `measured` argument of `judge` and the corner-radius part of `218bb1e1`. `image_inputs` returns the ring boxes only, and `image_keys` hashes the shared text, the digest and the ring boxes.
5. Proof kinds, `83b8cb54`, `185da681`, `c6848f03`, `a21c9009` (head filter) and `7e9e7e10` (the layout that develop landed with: the owner-check lines live in `look_records.py`): `judged_names`, `judged_lines`, `lacks_record`, `owner_lines`, `with_owner_lines`, `plan_rules`, the `unmeasured` keyword, `measure_verdict`, `_capture_stems`, and the `checks.md` sentence. Leave out the corner-radius assertion of `test_a_rule_with_measured_and_judgement_still_goes_to_the_reviewer`; it needs the measured values.
6. Tap-size for standalone links, `16f64a21`: the one new refusal that this hotfix takes. It changes the `controls` loop of the measure script in `ui_measure.py`, adds `tests/test_ui_tap_links.py`, drops the `link` case of `tests/test_ui_quality.py` (the link size case moves to the new test) and edits one sentence of `ux.md`.
7. Repoint part 2, `d76e6d87` (part 2 tests), `4c2dd02c` and `6bcc9c61`: `acceptance_span`, `acceptance_rows` and `repo_paths` in `plan_tests.py`, `plans.line_references`, and the lenient reader in `change_size.verified_test_ref_repair`. Leave out `unchanged_plan_test_problem` (part 1) and the part 1 tests of `tests/test_plan_acceptance.py`.

Same cause: Each fault has an earlier fix on develop only. Each fix helped on develop, but `main`'s installed projects never got it, because develop also holds new refusals. Searched `main`'s `.hooks` for other readers of reviewer rule lines (`split_rule_line`, `clean_line`, `records_for`, `STORE`): `pr_text.block_problem`, `ui_proof.look_problem` and `local_ui_proof._local_look_problem` read the stored dash form, which stays, so they need no change past the carry. The `building-flutter-apps` submodule, at `main`'s pinned revision, holds its own `.hooks`; it is a separate repository and this hotfix does not edit it. Not checked: whether an installed project runs that copy or Hard Eng's.
Single source: `PROOF_KINDS` stays the one owner of each rule's kind. `look_records.STORE` replaces `look.STORE`. `look.FIX_PART` is the one `Fix:` pattern. `plan_tests.acceptance_rows` becomes the one lenient reader of acceptance rows and `plans.line_references` the one `path::test` splitter for it.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; the client coordinator who asked for the hold on main asked for this hotfix; the hotfix merges only after the proof step.

## Acceptance + steps

- [ ] The attribution check moves to its own module with no change in behavior, and every handwritten file stays at or under 1000 lines → `tests/test_agent_hooks.py::test_check_rejects_claude_attribution_when_settings_turn_it_off`
- [ ] The reviewer's rule line is read in each of the three forms, a line with no verdict is refused, and the prompt asks for the dot form with no em dash → `tests/test_look.py::test_look_reads_each_rule_line_form_and_refuses_a_line_with_no_verdict`, `tests/test_look.py::test_the_prompt_form_needs_no_em_dash`, `tests/test_look.py::test_the_plan_scope_refuses_a_verdict_in_the_plain_form_too`
- [ ] A Fail line with no `Fix: <the change>` is refused as not done, and one with a fix stands → `tests/test_look.py::test_a_fail_line_that_cannot_stand_is_refused`
- [ ] The UI quality fixture answer names a fix on each Fail line, so its test still passes → `tests/test_look.py::test_look_reads_a_real_claude_answer`
- [ ] A clean look record of an earlier head carries per image when every reviewer input is the same, and stops carrying when one input changes → `tests/test_look_carry.py::test_a_clean_look_record_carries_to_a_new_head_with_the_same_reviewer_inputs`, `tests/test_look_carry.py::test_a_look_record_does_not_carry_when_one_reviewer_input_changed`
- [ ] A carried record backs the new head in `ship` and in the local proof, and reads the browser records of the evidence checkout → `tests/test_look_carry.py::test_a_carried_record_backs_the_new_head_in_ship_and_in_the_local_proof`, `tests/test_look_carry.py::test_a_carried_record_reads_the_browser_records_of_the_evidence_checkout`
- [ ] Only changed images go to the reviewer, the prompt says how many it holds back, `look --all` sends every image, and the earlier fixed Fail lines of a changed image go to the reviewer → `tests/test_look_carry.py::test_an_unchanged_image_is_not_sent_to_the_reviewer_again`, `tests/test_look_carry.py::test_a_run_whose_images_are_all_unchanged_does_not_start_the_reviewer`, `tests/test_look_carry.py::test_a_run_that_holds_back_images_tells_the_reviewer_and_all_forces_a_full_review`, `tests/test_look_carry.py::test_the_prompt_holds_the_earlier_fixed_finding_for_the_same_image_name`, `tests/test_look_carry.py::test_a_finding_of_an_image_that_has_not_changed_is_not_called_fixed`
- [ ] A record field that is missing never matches, so an old-format record never covers an image → `tests/test_look_carry.py::test_an_old_format_record_never_covers_and_a_new_format_record_still_does`
- [ ] The reviewer gets and decides only the rules with the `judgement` kind; a `measured` rule comes from the browser records, or from the reviewer when an image has no record; a `test` rule comes from the plan → `tests/test_look_proof_kinds.py::test_the_prompt_holds_only_the_rules_with_a_judgement_kind`, `tests/test_look_proof_kinds.py::test_a_reviewer_line_for_a_rule_without_judgement_is_ignored`, `tests/test_look_proof_kinds.py::test_the_block_gives_each_rule_a_line_and_names_the_owner`, `tests/test_look_proof_kinds.py::test_a_measure_finding_fails_the_measured_rules_and_the_run`, `tests/test_look_proof_kinds.py::test_a_test_rule_takes_its_line_from_the_plan`, `tests/test_look_proof_kinds.py::test_an_image_with_no_measure_record_leaves_the_measured_rules_to_the_reviewer`
- [ ] A reviewer Fail on a measured rule goes back as an earlier fix, and an owner Fail line does not → `tests/test_look_proof_kinds.py::test_a_reviewer_fail_on_a_measured_rule_is_sent_back_as_an_earlier_fix`, `tests/test_look_proof_kinds.py::test_an_owner_fail_line_is_not_sent_back_as_an_earlier_fix`
- [ ] An older capture with findings does not fail a page that a capture at the head shows clean → `tests/test_look_proof_kinds.py::test_an_older_capture_with_findings_does_not_fail_a_page_fixed_since`
- [ ] A rule with both the `measured` and `judgement` kinds still goes to the reviewer → `tests/test_look_proof_kinds.py::test_a_rule_with_measured_and_judgement_still_goes_to_the_reviewer`
- [ ] A standalone link gets the target-size check, a link inside a sentence stays exempt, and a 30 px link passes at 1280 px only → `tests/test_ui_tap_links.py::test_the_measure_flags_what_the_limits_and_the_exemption_leave`
- [ ] A Complete plan whose diff changes only `→ path::test` targets is judged as unchanged, for a plan with a proofless row and for an old form; any other change is still a changed plan → `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_with_a_proofless_row_gives_the_untouched_result`, `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_of_an_old_form_gives_the_untouched_result`, `tests/test_old_plan_test_ref_repair.py::test_a_repoint_with_another_change_is_still_judged_as_a_changed_plan`
- [ ] The skill links still resolve after the reference sentences change → `tests/test_skill_links.py::test_distributed_skill_links_resolve`
- [ ] Proof on a scratch copy of a separate test project, named by the coordinator of this work, with `.hooks` from the hotfix head: across 5 real runs of `look` on each copy, no Fail on a rule without the `judgement` kind, no form refusal, and every Fail names a fix; the clean rate per rule and each link that fails the new check on each copy are reported → N/A — no test can run a separate project from this repository; a separate verifier runs it on the PR head and the result goes in Verification

Steps:

1. Commit this plan as `features/look-hotfix/PLAN.md`.
2. One commit per hunk group, in this order: attribution move; rule-line forms; `Fix:` rule; carry with the empty-field match; proof kinds with the head filter; tap-size; repoint part 2. Each commit brings its tests from develop with the cuts named above, and the test helpers they need.
3. After each commit, run only its focused tests. After the last one, run the static gates, `check --plan-stage Ready --base origin/main`, `challenge` until clean for the exact head, then `check --plan-stage Complete --base origin/main` once.
4. Open the PR to `main`, run `pr-text`, wait for CI, run `ship --stage ready`, then stop. A separate verifier runs the proof step on that head.
5. After the go: `gh pr merge --merge --match-head-commit <sha>`, then `ship --stage delivered`, then join `main` into `develop` from a side branch and run `ship ready`, `ship --stage merge --pr <PR URL> --plan features/look-hotfix/PLAN.md` and `ship --stage delivered`.

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at `009927fb`, `tests/test_look.py`, `tests/test_plans.py`, `tests/test_agent_hooks.py`, `tests/test_old_plan_test_ref_repair.py`, `tests/test_ui_quality.py`, `tests/test_local_ui_proof.py`, `tests/test_plan_acceptance.py` and `tests/test_skill_links.py` pass: 449 tests in 60 s.
Execution: One builder in a new worktree off `origin/main`. First slice: the attribution move. A fresh reviewer runs `challenge` on the candidate head before the Complete check.

## Risks + recovery

1. The image key and the prompt text differ between this hotfix and develop. So after the join, a record written on `main` does not carry on develop, and the next `look` reviews again. That is safe: no false carry.
2. Proof kinds lets a browser record with findings fail `look`. `main`'s `ship` and local proof already refuse an After capture with findings. The head filter (`a21c9009`) keeps `look` equal to `ship`: an older capture with findings does not fail a page that the head shows clean. A `look` run on an image that is not an After capture, such as a Before image, can still fail on its own record; the proof step lists every such case.
3. The tap-size check is the one new refusal. A standalone link under 44 px at 390 or 768 px, or under 24 px at 1280 px, is a finding of `browser capture`, so a project with small links must fix them. The proof step lists each link that fails on each copy.
4. `look.py` grows toward the 1000-line limit. Recovery: the owner-check lines live in `look_records.py`, as on develop.
5. Join conflicts: `look.py`, `look_records.py`, `ui_proof.py`, `ui_measure.py`, `plans.py`, `plan_tests.py`, `change_size.py`, the three test files, `checks.md`, `ux.md`, `pyproject.toml` and `tests/fixtures/ui_quality/claude-answer.txt`. Rule: take develop's side in each conflict, then run the focused tests of every group on the join head.
6. Recovery for the hotfix as a whole: revert its merge on `main` with a new hotfix PR.
Not checked: the `building-flutter-apps` copy of the hooks; any installed project before the proof step.

## ux_reference

N/A — hook code, tests and skill sentences; no visible UI.

## Verification

Result: Pending
Evidence: Pending — focused tests per commit, the static gates, the Ready and Complete checks on the head, and the proof step result from the separate verifier.
E2E: Required — the proof step on scratch copies of separate test projects, as in the last Acceptance line.
Real service: N/A — the change calls no project service; the proof step runs the real reviewer CLIs.
Retro: Pending

Delivery target: Merge
Delivery: Pending — `hard-eng` passes on the PR to `main`, the merge on `main`, then the join PR merged into `develop`.
