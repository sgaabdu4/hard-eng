# Support one effort shipped over several PRs with a parent plan and a plan per step

Status: Ready

## Outcome + scope

An effort that ships over several PRs keeps one parent plan at Ready, and each step PR carries its own Complete plan that names the parent. Non-goals: ticking boxes by step inside one plan; checking that the parent's boxes change only in the last step.

## Sources + coverage

Sources: N/A — the request is the only source.

## Repository context

Owners: `.hooks/plan_parent.py` (new rules), `.hooks/plans.py` (`plan_stage` calls them; `plan_files` already finds `features/**/PLAN.md` at any depth), `.agents/skills/he/references/plan-checks.md` (rule text), `.agents/skills/he-plan/SKILL.md` and its `templates/PLAN.md` (one pointer each).
Same cause: N/A — a new capability, not a fix.
Single source: the `Parent:` rules have one owner, `plan_parent.py`. The `Parent:` line is read nowhere else. Searched `.hooks`, `tests` and the skills for `Parent:`; no other copy exists. The rule text lives only in plan-checks.md; the skill and the template point to it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous — Hard Eng design is the maintainer's delegated call; the decision (a child plan per step, no step-scoped ticking) was made before the build. Draft PR only; no merge.

## Acceptance + steps

- [x] A step plan that is Complete passes beside a Ready parent → `tests/test_plan_parent.py::test_a_complete_step_passes_while_its_parent_is_ready`
- [x] The first step PR adds the Ready parent and the Complete step together and passes the Complete stage → `tests/test_plan_parent.py::test_the_first_step_pr_adds_a_ready_parent_beside_its_complete_step`
- [x] A Ready plan with no step still blocks a Complete check → `tests/test_plan_parent.py::test_a_ready_plan_with_no_step_still_blocks_a_complete_check`
- [x] A step that names a missing parent fails → `tests/test_plan_parent.py::test_a_step_whose_parent_is_missing_fails`
- [x] A step whose parent is a Draft fails → `tests/test_plan_parent.py::test_a_step_whose_parent_is_a_draft_fails`
- [x] The parent is found in any letter case → `tests/test_plan_parent.py::test_a_parent_in_another_letter_case_is_found`
- [x] A step outside the parent's folder, a parent with its own parent and a second `Parent:` line fail → `tests/test_plan_parent.py::test_a_step_outside_its_parents_folder_fails`, `tests/test_plan_parent.py::test_a_parent_that_has_a_parent_fails`, `tests/test_plan_parent.py::test_two_parent_lines_fail`
- [x] A parent cannot be Complete while a step is not → `tests/test_plan_parent.py::test_a_parent_cannot_close_while_a_step_is_open`
- [x] Separate sibling plans per step with no `Parent:` line keep passing → `tests/test_plan_parent.py::test_separate_sibling_plans_without_a_parent_line_keep_passing`
- [x] The skill stays under the Codex size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`

## Baseline + execution

Result: Passed
Evidence: 2026-11-21, develop 8c9b8b2a: `tests/test_plans.py`, `tests/test_plan_*.py`, `tests/test_change_size.py` and `tests/test_skill_links.py` all passed on the starting code before the change.
Execution: One builder in a task worktree; the independent review runs on the finished branch.

## Risks + recovery

N/A — a plan without a `Parent:` line takes none of the new code paths except a header read; a revert restores the old check.

## ux_reference

N/A — command line checks and text only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no browser, app or API journey; the real check run is in Evidence.
Real service: N/A — the change calls no outside service.
Retro: Required on Complete.
Delivery target: PR
Delivery: Pending — draft PR to develop; develop is frozen until the release reaches main.
