# Only the Swift checks of a generated workflow run on macOS

Status: Complete

## Outcome + scope

A generated workflow for a project with a Swift group runs only the affected Swift groups on a macOS runner, and every other affected group on the Linux runner. It has four jobs: `impact`, `hard-eng-linux` (every group except Swift), `hard-eng-apple` (only the Swift groups, only when `impact` prints `apple=true`, on `${{ vars.CI_MACOS_RUNS_ON && fromJSON(vars.CI_MACOS_RUNS_ON) || 'macos-latest' }}`) and `hard-eng`, a Linux job that passes only when the other jobs did, so the required check keeps its name. `check` and `impact` take `--only-language` and `--skip-language`. Update moves an earlier generated Swift workflow to this shape once. Non-goals: the workflow for projects without Swift, the names in `shipping.checks`, this repository's Canary and release workflows, the `runner=` output values.

## Repository context

Owners: `impact`, the language filter and the Swift job layout in `.hooks/ci_jobs.py` (moved there from `.hooks/ci_setup.py`, which was at the 1000-line limit), the filter flags and the `impact` wrapper in `.hooks/hard-eng.py`, `workflow_budget` in `.hooks/ci_setup.py`.
Same cause: the generated check job ran every group on the macOS runner once a Swift group was affected, so any change to a workflow or to `hard-eng.gates.json`, which selects every group, billed the whole check at the macOS rate. The earlier fix for the runner choice (`features/ci-runs-on-variable/PLAN.md`) moved the Linux runner onto `CI_RUNS_ON` and left the macOS job whole. A search of the repository for `runs-on`, `impact_runner` and `runner=` found no other writer of the job layout; `canary.yml` and `release-source.yml` run only in this repository.
`hard-eng` is now an aggregate. `shipping.py` rejects a skipped required check ("gate its steps, not the job") and `update_pr.py` treats a skipped named check as failing, so the Swift job can never be the required check. `canary.yml` already ends in an aggregate `canary` job.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this change on 2026-10-30: a pull request into `develop`, merged when green, then a release pull request to `main`. Decided: the Linux job has no `needs`, so it starts at once; the Swift job runs unless `impact` prints `apple=false`, and a failed impact step prints `apple=true`, so a broken step runs Swift instead of skipping it; the dependency-install gates of a kept group's ancestors run in both halves because the Swift tests build with `--no-pub`; a customised workflow is left alone with a note.

## Acceptance + steps

- [x] `impact` prints `apple=true` when a Swift group is affected and `apple=false` otherwise, and on the already-proven path → `tests/test_swift.py::test_impact_prints_the_runner_and_whether_swift_is_affected` and `tests/test_gate_speed.py::test_impact_takes_the_fast_path_when_the_change_is_already_proven`.
- [x] The generated Swift workflow has the four jobs with their runners, conditions, timeouts and language flags → `tests/test_apple_jobs.py::test_swift_project_splits_the_check_by_runner` and `tests/test_apple_jobs.py::test_each_check_job_runs_its_own_languages`.
- [x] `hard-eng` passes only when `impact` and the Linux job passed and the Swift job passed or was skipped → `tests/test_apple_jobs.py::test_the_required_check_passes_only_when_every_needed_job_did`.
- [x] A failed impact step runs the Swift job → `tests/test_runner_variable.py::test_a_failed_impact_script_still_runs_the_swift_job`.
- [x] The language filter keeps every gate in one half or the other, and `check` applies it → `tests/test_apple_jobs.py::test_the_two_halves_together_run_every_gate` and `tests/test_apple_jobs.py::test_check_applies_the_language_filter`.
- [x] The filter keeps a Swift group's dependency installs and drops the shared group from the Swift half → `tests/test_apple_jobs.py::test_only_a_language_keeps_its_groups_and_their_dependency_installs`.
- [x] A workflow generated before this change moves to the new shape once, then stays unchanged → `tests/test_apple_jobs.py::test_previous_generation_splits_once` and `tests/test_runner_variable.py::test_older_workflow_moves_to_the_runner_variable`.
- [x] Custom steps are kept in both halves and later jobs stay in place → `tests/test_apple_jobs.py::test_custom_lines_and_later_jobs_stay`.
- [x] A customised job header, impact outputs or check command is left alone with a note → `tests/test_apple_jobs.py::test_customised_previous_generation_is_left_with_a_note`.
- [x] A project without Swift keeps its single `hard-eng` job → `tests/test_apple_jobs.py::test_new_install_without_swift_keeps_one_job`.
- [x] The CI time budget lands on the two worker jobs → `tests/test_apple_jobs.py::test_generated_budget_applies_to_the_check_jobs`.
- [x] The README and the gates reference describe the jobs and `CI_MACOS_RUNS_ON` → N/A — documentation text, read in the diff.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 251f265: `tests/test_swift.py`, `tests/test_ci_setup.py`, `tests/test_runner_variable.py` and `tests/test_tool_environment.py` passed (143 tests) before the change. Run against the old `ci_setup.py`, the new job layout and filter tests fail.
Execution: One builder; the module and the filter first, then the migration, then the tests and the documents.

## Risks + recovery

`ship` compares the duration of `hard-eng` with `shipping.ci_seconds`; the aggregate lasts seconds, so `timeout-minutes` on `hard-eng-linux` and `hard-eng-apple` now bounds the real work. A custom step in the old check job is copied into both halves. A runner label list in `CI_MACOS_RUNS_ON` that is not JSON fails the Swift job. Recovery: unset the variable, or revert the commit and rerun setup.

## ux_reference

N/A — workflow and setup change with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Draft --base origin/develop` on the branch: all 20 gates passed, 2037 tests passed, line coverage 91.31%. A first run failed the `duplicates` gate on a repeated migration test step; the second commit fixes it and the rerun passed. `actionlint` and `zizmor --persona=auditor` report nothing on a generated Swift workflow.
E2E: N/A — the tests run the generated steps in a real shell and the real setup migration on written workflow files; the runner GitHub picks for a hosted or self-hosted job is decided from the variable and is not provable here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
