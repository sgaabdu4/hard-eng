# Fix Two Look Faults Found on a Real Run

Status: Ready

## Outcome + scope

Fix two `look` faults found on a real run after the merged work on the carry and the px guard:
1. An old-format clean record covered a new head. `covering_record` compared a missing `inputs` field with a missing key, and a record image that is not in the run matched too. A record that lacks a compared field must never cover or count as changed. Every copy of this compare goes through one helper in `.hooks/look_records.py`.
2. A fresh Claude reviewer wrote every rule line as `Rule: Pass. text` with no dash, and `look` refused the whole run. Make the reviewer form need no dash character: the prompt states `- <rule>: <verdict>. <what you saw>` with a period after the verdict word, and `look` accepts `Rule: Pass. text`, `Rule: Pass - text` and `Rule: Pass — text`. Every other form check stays.

Non-goals: changing `split_rule_line` or the PR block form, and any other look check.

## Sources + coverage

Sources: the maintainer's brief of 2026-11-24 and the sealed logs of three real runs, read in full. The logs hold a client's screen text, so this plan gives counts and forms only.
Reviewer: N/A — two small faults with a stated cause.
Deliverables: None

- Fault 1, empty fields match: In scope — one helper owns the compare
- Fault 2, rule line form: In scope — the prompt form needs no em dash, and the parser takes three forms

## Repository context

Owners:
- `.hooks/look_records.py` owns the carry, `covering_record`, `earlier_fixes` and `combined`.
- `.hooks/look.py` owns `PROMPT`, `clean_line` and `judge`.
- `.hooks/plans.py` owns `split_rule_line`; plan UX Rules, `ui_proof`, the PR block and the Stop path read it, so it stays as it is.

Same cause 1: three places compared a record field with a wanted value without checking that the field exists: `covering_record` (`inputs`), `carried_record` (`inputs` through a guard) and `earlier_fixes` (`file`, and `sha256`, where a missing digest counts as changed). The compare moves to one helper.
Same cause 2: the reviewer form was one character the reviewer may not write. Proof of cause: in the failing run, all 16 rule lines have the form `Rule: Pass. text` (a period, no dash), and the parser needs a dash after the verdict. The two other runs used the em dash and parsed. The user rule against em dashes is the likely reason the reviewer left it out; the logs cannot prove that part.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.
Review declined: A fresh run of the old prompt to prove the cause again :: the saved answer of the failing run already shows the form, and a new run costs a reviewer session for no new fact.

## Acceptance + steps

- [ ] An old-format clean record (no `inputs`, no per-image `file`) never covers a new head, and a new-format record with equal inputs still covers → `tests/test_look_carry.py::test_an_old_format_record_never_covers_and_a_new_format_record_still_does`.
- [ ] A missing `file` or `sha256` in an earlier finding is not read as a changed image → `tests/test_look_carry.py::test_a_finding_of_an_image_that_has_not_changed_is_not_called_fixed`.
- [ ] Each of the three line forms parses, and a line with no verdict word is still refused → `tests/test_look.py::test_look_reads_each_rule_line_form_and_refuses_a_line_with_no_verdict`.
- [ ] The prompt states the dash-free form and holds no em dash → `tests/test_look.py::test_the_prompt_form_needs_no_em_dash`.
- [ ] The plan scope guard follows the same forms, so `Rule: Pass. text` in `## Outcome + scope` is refused as a verdict leak → `tests/test_look.py::test_the_plan_scope_refuses_a_verdict_in_the_plain_form_too`.
- [ ] Skill and reference links and size limits pass → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: Worktree from `origin/develop` at `6a346bcd`; the new tests fail there before each fix.
Execution: One commit for each fault with its failing test first.

## Risks + recovery

The prompt text feeds the image key, so each existing clean record stops carrying once, and the next `look` reviews again. The plan scope guard shares `clean_line`, so `Rule: Pass. text` inside `## Outcome + scope` is now refused as a verdict leak; this is intended. Recovery: revert the commits on `develop`.

## ux_reference

N/A — Hard Eng is a CLI and hook toolkit with no visual application UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — a CLI and hook fix, verified by fixture tests.
Real service: N/A — no deployed service is involved.
Retro: Pending

Delivery target: Merge
Delivery: Pending — check, challenge, PR to `develop`, CI, merge.
