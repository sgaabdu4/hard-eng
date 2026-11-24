# Decide each Usability rule by its own proof kind in look

Status: Ready

## Outcome + scope

`look` sends the reviewer only the Usability rules that have the `judgement` kind. The `Look review:` block still gives one line per rule. A rule with only the `measured` or `test` kind takes its line from its owner check, never from the reviewer. Non-goals: the reviewer's wording, the measure script, the plan check.

## Sources + coverage

Sources: N/A — the request is the only source; the builder brief names no document or call.

## Repository context

Owners: `PROOF_KINDS` in `.hooks/ui_measure.py` (kind of each rule); `.hooks/look.py` (prompt, `judge`, record, block); `.hooks/ui_proof.py` (browser records); `.hooks/plans.py` (`ux_rules`, `rule_lines`, `split_rule_line`).
Where each kind's verdict comes from today: `judgement` is the reviewer's line, as it should be. `measured` is also the reviewer's line, although `browser capture` records findings per width and `ship` refuses a capture set with findings. `test` is also the reviewer's line, although the plan's `Rules:` line holds the plan's own verdict and `ux_rules` refuses a Fail there. After this change the reviewer decides only `judgement`, plus a `measured` rule for an image that has no measure record (a native screen has none, and `ship` never asks for one).
Same cause: Searched `PROOF_KINDS`, rule names and the sentence "judge a rule that an image cannot show from its test or code" in `.hooks`, `.agents/skills`, `docs`, `features` and `tests`. Other places that list rules by kind: the gate table in `features/ui-quality-enforcement/PLAN.md` (a test compares it with `PROOF_KINDS`), the line "For a rule that an image cannot show (for example Time, Audit, Performance)" in `.agents/skills/he-plan/references/ux.md` and its copies in the two skill sources (submodules, not edited here), the `PROOF_KINDS` copy in the `building-flutter-apps` submodule `.hooks/ui_measure.py` (its own repository, not edited here), and the sentence in `.agents/skills/code-review/references/review.md` (a reviewer instruction, still right). No earlier fix of this cause.
Single source: `PROOF_KINDS` stays the one owner of each rule's kind. `look.py` and `ui_proof.py` read it and copy no rule list. The plan's `Rules:` lines stay the one owner of a test rule's verdict, and the browser records stay the one owner of a measured rule's verdict. Searched `.hooks` and `tests` for lists of rule names: only `plans.usability_rules` and `PROOF_KINDS` hold them.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [ ] The prompt holds only the rules with the `judgement` kind → `tests/test_look_proof_kinds.py::test_the_prompt_holds_only_the_rules_with_a_judgement_kind`.
- [ ] A reviewer line for a rule without `judgement` cannot fail the run and is not counted as missing → `tests/test_look_proof_kinds.py::test_a_reviewer_line_for_a_rule_without_judgement_is_ignored`.
- [ ] The record and the block give one line per rule, and each line without `judgement` names its owner → `tests/test_look_proof_kinds.py::test_the_block_gives_each_rule_a_line_and_names_the_owner`.
- [ ] A measure record with a finding fails the measured-only rules and the run → `tests/test_look_proof_kinds.py::test_a_measure_finding_fails_the_measured_rules_and_the_run`.
- [ ] A plan Fail for a test rule fails the run, and with no plan the line says the plan check decides → `tests/test_look_proof_kinds.py::test_a_test_rule_takes_its_line_from_the_plan`.
- [ ] An image with no measure record (a mockup or a native screen) leaves the `measured` rules to the reviewer → `tests/test_look_proof_kinds.py::test_an_image_with_no_measure_record_leaves_the_measured_rules_to_the_reviewer`.
- [ ] A rule with `measured` and `judgement` still goes to the reviewer with its measured values → `tests/test_look_proof_kinds.py::test_a_rule_with_measured_and_judgement_still_goes_to_the_reviewer`.
- [ ] An owner Fail line never returns to the reviewer as an earlier fix → `tests/test_look_proof_kinds.py::test_an_owner_fail_line_is_not_sent_back_as_an_earlier_fix`.
- [ ] The skill links still resolve after the one-line reference change → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-24, develop 18f9f803: `tests/test_look.py tests/test_look_carry.py tests/test_look_px.py tests/test_ui_quality.py tests/test_local_ui_proof.py tests/test_shipping_ui_evidence.py` gave `163 passed` in 168 s.
Execution: One builder (this session). Another builder has `fix/count-guard` open on `look.py`; if it merges first, rebase and keep both changes.

## Risks + recovery

The prompt changes, so the image key changes, and old clean records stop carrying once; the next `look` run reviews each image again. A revert restores the old prompt and keys.

## ux_reference

N/A — no visible UI; hook code and a reference line only.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no user journey of an installed app changes; the focused tests run `look` with a fake reviewer.
Real service: N/A — the change calls no outside service; it reads local browser records and the committed plan.
Retro: Pending

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
