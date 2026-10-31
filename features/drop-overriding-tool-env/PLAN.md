# Setup drops the step env mapping that overrides the runner's tool directories

Status: Complete

## Outcome + scope

Setup and update remove the `MISE_DATA_DIR`, `MISE_CACHE_DIR`, `MISE_STATE_DIR` and `BUN_INSTALL_CACHE_DIR` mapping lines (`NAME: ${{ runner.temp }}/hard-eng-tools/...`) from a workflow that already exports the same variable in the `${NAME:-default}` form. Non-goals: a mapping in a workflow without the exporting step, a custom directory.

## Repository context

Owners: `migrate_tool_environment` in `.hooks/ci_setup.py`.
Same cause: the previous two changes moved only the `echo` lines. Older generated workflows also carried the same four variables in the env mapping of the required-checks step. A step env value beats a value written to the job environment file, so a web project whose export step was already in the new form still ran its checks with the runner temp folder: its log shows the runner's persistent tool directory in the first steps and the throwaway one in the checks step, and the tools downloaded again. Searched the generated templates of every historical revision (replay of each through `configure_ci`): the mapping is in every revision before the move to the `echo` lines; the current template has none.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this stream on 2026-10-31 (edit, push, open pull requests into `develop`, no release). Decided: remove the mapping only when the same file holds the `${NAME:-` export for that variable, so a workflow that never exports it keeps working.

## Acceptance + steps

- [x] A leftover mapping next to the new export is removed on the next setup, once → `tests/test_tool_environment.py::test_leftover_env_mapping_stops_overriding_the_runner_directories`.
- [x] The generated workflow and the `echo` migration are unchanged → `tests/test_tool_environment.py::test_older_workflow_keeps_runner_directories_after_the_update`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 799d5cf: `tests/test_tool_environment.py` 6 passed. The new test failed before the change (mapping lines kept).
Execution: One builder; test first, then the regex.

## Risks + recovery

A mapping line removed from a customised workflow that relied on it for a step that runs before the export step. The export step is the first step of the generated job. Recovery: revert the commit.

## ux_reference

N/A — setup change with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed and 2094 tests passed. Earlier runs failed `duplicates` (two near-identical test set-ups) and the no-switch-off rule on a stale base; the set-up moved into one helper and the branch was rebased.
E2E: N/A — the test runs the real setup migration on a written workflow.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
