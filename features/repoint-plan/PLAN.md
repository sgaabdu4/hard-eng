# Repointing test names in an old Complete plan; removing a test that an old plan names

Status: Complete

## Outcome + scope

An old Complete plan whose only change is new targets after `→` on its checkbox lines is judged as unchanged, and its new targets must exist. A change that removes or renames a test that any Complete plan names is refused in that change, whatever the form of the old plan. The refusal names the plan and the line. Non-goals: any change to the rules for new plans, and to `Same cause` or `Retro` references.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24.

## Repository context

Owners: `.hooks/plan_tests.py` (`unchanged_plan_test_problem`, `acceptance_rows`) reads the acceptance rows of an old plan; `.hooks/change_size.py` (`verified_test_ref_repair`) decides that a plan changed only its targets.
Same cause: the check that judges plans which are not in the change (`unchanged_plan_test_problem`, from 2026-11-19) read each old plan through the strict reader `plan_sections`, and matched a plan's path text against the changed names with no normalising. So an old plan that lacks a section added later (`ux_reference`), holds a not-applicable mark with no reason, or writes `./tests/...` was skipped without a word. The repair check (`verified_test_ref_repair`, plan `old-plan-test-ref-repair`) called the strict `acceptance_tests`, so an old plan with one checkbox that names no proof was refused whole when only its targets changed. Both now read the section with one lenient reader. Searched `plan_sections(`, `acceptance_references`, `acceptance_tests(` and `_acceptance_row_refs` in `.hooks`: the other users read plans that are in the change and need the strict form. The earlier fix of 2026-11-24 (`e9384304`) closed the bad-form-line hole only. The repair check no longer validates the old plan at all: an untouched old plan is never validated, so a plan whose only change is its targets gets the same result. The original escape of the four removed tests could not be rerun here: the repository holds the check from 2026-11-19, so the cause stands for the forms the check still skipped (plan without a later section, not-applicable mark with no reason, `./` path); the first sighting is not determined from this repository.
Single source: `acceptance_rows` in `plan_tests.py` is the one reader of the acceptance rows, with their line numbers; `_acceptance_row_refs` and the copy in `acceptance_references` use it. `_repo_paths` moves there too, so both checks match a target path to a changed name one way.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] Repointing an old plan that has a checkbox with no named proof counts as unchanged, and gives the result that the untouched plan gives at each stage → `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_with_a_proofless_row_gives_the_untouched_result`
- [x] Repointing an old plan that lacks a section added later, or holds a not-applicable mark with no reason, gives the untouched result, so the refusal's own fix works → `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_of_an_old_form_gives_the_untouched_result`
- [x] A repoint with any other change, or to a missing test, is still judged as a changed plan → `tests/test_old_plan_test_ref_repair.py::test_a_repoint_with_another_change_is_still_judged_as_a_changed_plan`
- [x] Removing a test that an unchanged old plan names is refused with the plan and its line, for each old form → `tests/test_plan_acceptance.py::test_removing_a_named_test_is_refused_whatever_the_form_of_the_old_plan`
- [x] One reader gives the same rows as the strict reader, and a plan with no acceptance heading names no rows → `tests/test_plan_acceptance.py::test_the_lenient_reader_gives_the_rows_of_the_strict_reader`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`18f9f803`), the repo's plan tests pass. The new tests fail there: 15 of 21 selected cases fail (the six removal cases for old forms do not raise, the plain removal lacks the line number, the six repoint cases of a proofless row and the missing-target repoint are refused as a new plan); the six other near-miss cases already pass and guard against loosening.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then the reader, then the repair.

## Risks + recovery

The lenient reader judges more old plans, so a project can see a refusal for a plan that the old check skipped. That is the fault: the plan names a test that no longer exists. Recovery: revert the commits.

## ux_reference

N/A — hook validation logic and tests only; no visible UI.

## Verification

Result: Passed
Evidence: `check --base origin/develop --plan-stage Ready` passed all gates (7914 tests, 876 s). The plan check took 0.335 and 0.323 s on develop and 0.336 and 0.317 s on this branch (`judged_stage` at Ready, two runs each). The independent review found one fault in the first head (the repair validated the old plan strictly, so the refusal's own fix failed for old forms); it is fixed with a test, and the review of the next head is clean. Reading `install_new` in `release_canary.py`: no new-project flow holds a Complete plan that names a test, so no flow reaches the new refusal. Not checked: `local_ui_proof` with a real `ux_reference` record on a repointed plan (the review read it as not strict-parsing).
E2E: N/A — hook tests run real temporary Git repositories with a base and a branch commit.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Escaped bug: a change that removed tests named by an old Complete plan passed every gate; the gate is the plan check, and the new cases fail on the base revision → `tests/test_plan_acceptance.py::test_removing_a_named_test_is_refused_whatever_the_form_of_the_old_plan`. Review correction: the repair check validated the old plan strictly, which refused the refusal's own fix for old forms → `tests/test_old_plan_test_ref_repair.py::test_repointing_an_old_plan_of_an_old_form_gives_the_untouched_result`. Review declined: the new old-form test keeps the old test, so it does not show the refusal and then its fix; the two halves are each proved by the two tests above. Ran too late: none. Single reader: `tests/test_plan_acceptance.py::test_the_lenient_reader_gives_the_rows_of_the_strict_reader`.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
