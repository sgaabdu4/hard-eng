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
- [x] A Ready parent does not ride along with a Draft step; a parent with an unknown status fails; a step cannot be open while its parent is Complete → `tests/test_plan_parent.py::test_a_ready_parent_does_not_ride_along_with_a_draft_step`, `tests/test_plan_parent.py::test_a_parent_with_an_unknown_status_fails`, `tests/test_plan_parent.py::test_a_step_cannot_be_open_while_its_parent_is_complete`
- [x] The PR text check skips a parent plan only beside a step that sits below it, in any path form, and not for a document → `tests/test_plan_parent.py::test_the_pr_text_check_skips_a_parent_plan_beside_its_step`, `tests/test_plan_parent.py::test_a_document_that_names_a_plan_as_its_parent_does_not_skip_it`, `tests/test_plan_parent.py::test_a_parent_path_with_a_dot_segment_is_found`
- [x] The skill stays under the Codex size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`

## Baseline + execution

Result: Passed
Evidence: 2026-11-21, develop 8c9b8b2a checked out in the task worktree: `pytest tests/test_plans.py tests/test_plan_acceptance.py tests/test_plan_controls.py tests/test_plan_coverage.py tests/test_plan_runs.py tests/test_planning_handoffs.py tests/test_change_size.py tests/test_skill_links.py` gave 491 passed, exit 0.
Execution: One builder in a task worktree; the independent review runs on the finished branch.

## Risks + recovery

N/A — a plan without a `Parent:` line takes none of the new code paths except a header read; a revert restores the old check.

## ux_reference

N/A — command line checks and text only; no visible UI.

## Verification

Result: Passed
Evidence: Real runs of `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` in a scratch Git repository with a local bare origin, hooks copied from this branch, one passing shared check, a Ready parent `features/effort/PLAN.md` and a step `features/effort/step-1/PLAN.md` with a `Parent:` line. (1) Step Complete, parent Ready, both new on the branch: exit 0, "build checks passed". (2) The step names `features/gone/PLAN.md`: exit 1, "Parent features/gone/PLAN.md is not a plan; name an existing plan". (3) The parent is Draft: exit 1, "Parent features/effort/PLAN.md is Draft; it must be Ready or Complete". Before the ride-along rule, run (1) failed with "features/effort/PLAN.md: plan is Ready; this check requires Complete". Tests: `tests/test_plan_parent.py` 17 passed; with `tests/test_pr_text.py`, `tests/test_ui_quality.py` and `tests/test_skill_links.py` 168 passed. Static gates on the branch (format, lint, complexity, annotations, types, dead-code, duplicates, declarations, shipped-format, shipped-focused-tests, actionlint, zizmor, shellcheck, gitleaks files, semgrep): all exit 0. Not checked: a hook timing comparison (the added work reads plan headers only; the one timing run was noise-level, 0.76 to 1.37 s on both versions).
Review: Challenge round 1 (4f974402) gave 5 findings. Fixed with failing tests first: a Ready parent rode along beside a Draft step (now needs a step at the stage); a parent with an unknown status passed (now Ready or Complete only); a step open under a Complete parent passed; the PR text check refused a valid first UI step (it now skips a parent beside its step). Reader check: Codex (`codex exec`, read-only, did not write the text) read the diff of the changed skill text twice; pass 1 quoted five sentences to reread and two trimmed rules (success/failure/recovery outcomes, never call a change small yourself); both rules are back, the UI baseline sentence moved verbatim to `ux.md`, and the step rules in plan-checks.md were reworded; pass 2 found no changed meaning beyond the added step rules. Round 2 (0e13f960) gave 5 findings: the PR text parent skip now needs a plan path, a step folder below the parent and any path form (fixed); the skill names the nested location (fixed); the Reader record is here (fixed). Declined: deleting a parent while its unchanged step stays and an unrelated Complete plan is added passes, because a step plan is judged only when it changes and removing a parent is a deliberate act that no other plan link is checked for.
E2E: N/A — no browser, app or API journey; the real check run is in Evidence.
Real service: N/A — the change calls no outside service.
Retro: (1) Escaped bug: the first draft let any Complete plan waive a Ready parent and let a document pass as a step → caught by the independent review, not by a gate: no new rule, the tests now name both cases. (2) Ran too late: the skill size limit failed after the text was written → None, the existing size test caught it and the rule text moved to a reference. (3) The first Ready check timed out in the tests stage on a loaded machine → None, a limit hit, not a failure.
Delivery target: PR
Delivery: Pending — draft PR to develop; develop is frozen until the release reaches main.
