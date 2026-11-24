# Repointing test names in an old Complete plan; removing a test that an old plan names

Status: Ready

## Outcome + scope

An old Complete plan whose only change is new targets after `→` on its checkbox lines is judged as unchanged, and its new targets must exist. A change that removes or renames a test that any Complete plan names is refused in that change, whatever the form of the old plan. The refusal names the plan and the line. Non-goals: any change to the rules for new plans, and to `Same cause` or `Retro` references.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24.

## Repository context

Owners: `.hooks/plan_tests.py` (`unchanged_plan_test_problem`, `acceptance_rows`) reads the acceptance rows of an old plan; `.hooks/change_size.py` (`verified_test_ref_repair`) decides that a plan changed only its targets.
Same cause: the check that judges plans which are not in the change (`unchanged_plan_test_problem`, from 2026-11-19) read each old plan through the strict reader `plan_sections`, and matched a plan's path text against the changed names with no normalising. So an old plan that lacks a section added later (`ux_reference`), holds a bare `N/A`, or writes `./tests/...` was skipped without a word. The repair check (`verified_test_ref_repair`, plan `old-plan-test-ref-repair`) called the strict `acceptance_tests`, so an old plan with one checkbox that names no proof was refused whole when only its targets changed. Both now read the section with one lenient reader. Searched `plan_sections(`, `acceptance_references`, `acceptance_tests(` and `_acceptance_row_refs` in `.hooks`: the other users read plans that are in the change and need the strict form. The earlier fix of 2026-11-24 (`e9384304`) closed the bad-form-line hole only.
Single source: `acceptance_rows` in `plan_tests.py` is the one reader of the acceptance rows, with their line numbers; `_acceptance_row_refs` and the copy in `acceptance_references` use it. `_repo_paths` moves there too, so both checks match a target path to a changed name one way.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [ ] Repointing an old plan that has a checkbox with no named proof counts as unchanged, and gives the result that the untouched plan gives at each stage → `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_with_a_proofless_row_gives_the_untouched_result`
- [ ] A repoint with any other change, or to a missing test, is still judged as a changed plan → `tests/test_old_plan_test_ref_repair.py::test_a_repoint_with_another_change_is_still_judged_as_a_changed_plan`
- [ ] Removing a test that an unchanged old plan names is refused with the plan and its line, for each old form → `tests/test_plan_acceptance.py::test_removing_a_named_test_is_refused_whatever_the_form_of_the_old_plan`
- [ ] One reader gives the same rows as the strict reader, and a plan with no acceptance heading names no rows → `tests/test_plan_acceptance.py::test_the_lenient_reader_gives_the_rows_of_the_strict_reader`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`18f9f803`), the repo's plan tests pass. The new tests fail there for the forms named above; the failing output is in the first commit's run.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then the reader, then the repair.

## Risks + recovery

The lenient reader judges more old plans, so a project can see a refusal for a plan that the old check skipped. That is the fault: the plan names a test that no longer exists. Recovery: revert the commits.

## ux_reference

N/A — hook validation logic and tests only; no visible UI.

## Verification

Result: Pending
Evidence: Pending — the focused tests, the static gates and the Complete check on the head.
E2E: N/A — hook tests run real temporary Git repositories with a base and a branch commit.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Pending until task end.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
