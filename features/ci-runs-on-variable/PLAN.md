# Generated workflows pick their Linux runner from a repository variable

Status: Complete

## Outcome + scope

Every `runs-on` that Hard Eng writes or migrates uses `${{ vars.CI_RUNS_ON && fromJSON(vars.CI_RUNS_ON) || 'ubuntu-latest' }}`. A private repository can set `CI_RUNS_ON` to a JSON runner value, such as a label list for a self-hosted runner. A public repository leaves it unset and keeps `ubuntu-latest`. A failed impact step no longer falls back to `macos-latest`; only a detected Swift group picks macOS. Non-goals: the Canary and release workflows of this repository, the `impact` output values, the Zizmor rule handling in `.hooks/gitleaks_scan.py`.

## Repository context

Owners: `.github/workflows/hard-eng.yml` (copied whole into new installs), `.github/workflows/pr-text.yml` (replaced whole on update), and `RUNNER_JOB`, `CHECK_JOB`, `RUNNER_HEADER`, `migrate_swift_runner` and the new `migrate_runner_variable` in `.hooks/ci_setup.py`.
Same cause: one cause, the generated jobs named a hosted runner. A search of the repository for `runs-on` found no other writer; `canary.yml` and `release-source.yml` run only in this repository.
`impact_runner()` and the `runner=` output keep plain labels: a job output is a string, not an expression, so the variable cannot travel through it, and workflows that already compare the output with `ubuntu-latest` keep working. The check job decides instead: `macos-latest` only when the output says so, otherwise the variable expression.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-10-29 for this change as a pull request into `develop`, without a merge. The variable name `CI_RUNS_ON` is fixed by the request. Decided: the migration edits only the generated job headers and the macOS fallback text, so a workflow with its own `runs-on` value stays as it is.

## Acceptance + steps

- [x] New installs and the shipped `pr-text.yml` take their runner from the variable → `tests/test_runner_variable.py::test_shipped_workflows_take_their_runner_from_the_variable`.
- [x] The generated Swift workflow runs the impact job on the variable runner and picks macOS only when impact says so → `tests/test_swift.py::test_swift_workflow_selects_runner`.
- [x] A failed impact script writes a Linux runner, not `macos-latest` → `tests/test_runner_variable.py::test_a_failed_impact_script_does_not_pick_macos`.
- [x] An install generated before the variable, with or without the Swift jobs, moves to it once and then stays unchanged → `tests/test_runner_variable.py::test_older_workflow_moves_to_the_runner_variable`.
- [x] A plain workflow that gains a Swift group still gets the impact job, whether it was generated before or after the variable → `tests/test_runner_variable.py::test_older_workflow_moves_to_the_runner_variable` and `tests/test_swift.py::test_existing_workflow_gains_the_runner_job_once`.
- [x] A custom `runs-on` is left alone, with a note when a Swift group needs the impact job → `tests/test_runner_variable.py::test_a_custom_runner_stays_when_the_variable_arrives` and `tests/test_swift.py::test_customised_workflow_is_left_with_a_note`.
- [x] The impact output contract is unchanged → `tests/test_swift.py::test_impact_runner_is_macos_only_for_swift`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 194d174: `tests/test_swift.py`, `tests/test_ci_setup.py` and `tests/test_ci_launcher.py` passed before the change. Run against the old `ci_setup.py`, the new migration and Swift workflow tests failed.
Execution: One builder; template and constants first, then the migration, then the tests.

## Risks + recovery

`fromJSON` fails the job if `CI_RUNS_ON` is set to text that is not JSON, such as `ubuntu-24.04` without quotes. The README names the JSON form. A Swift check can still run on paid `macos-latest` when a Swift group is selected; that is intended. Recovery: unset the variable.

## ux_reference

N/A — workflow and setup change with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed, 2005 tests passed, line coverage 91.22%. Zizmor (auditor persona) and actionlint report nothing on the new `runs-on` values, in the template and in a generated Swift workflow. The pre-push command on the final commit also passed.
E2E: N/A — the tests run the generated impact step in a real shell and the real setup migration on written workflow files; the runner a hosted or self-hosted job picks is decided by GitHub from the variable and is not provable here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
