# Setup moves the tool-directory lines of project-owned workflows too

Status: Complete

## Outcome + scope

Setup and update rewrite the four generated `MISE_DATA_DIR`, `MISE_CACHE_DIR`, `MISE_STATE_DIR` and `BUN_INSTALL_CACHE_DIR` lines to the `${NAME:-default}` form in every workflow file, not only `hard-eng.yml`. Non-goals: a custom directory, the pre-Bun `env:` mapping form (its `${{ runner.temp }}` cannot read the runner's own export; the CI cache check in a later change reports it).

## Repository context

Owners: `migrate_tool_environment` and `configure_ci` in `.hooks/ci_setup.py`.
Same cause: the migration of the previous change ran only on `.github/workflows/hard-eng.yml`. A web monorepo, a mobile app monorepo and a second web project keep the Hard Eng steps in a project-owned `ci.yml`, so the latest release left their lines unchanged and every run on a self-hosted runner with a persistent `MISE_DATA_DIR` ignored it and downloaded its tools again (about 70 s per run). A replay of every historical `hard-eng.yml` template through `configure_ci` shows each echo-form template since the Bun move now migrates; templates older than that keep the `env:` mapping form, which no migration touches.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this stream on 2026-10-31 (edit, push, open pull requests into `develop`, no release). Decided: rewrite only lines equal to the generated text, in any `.github/workflows/*.yml|yaml`; such a change makes an update pull request leave the scaffold-only path, which is correct because CI changed.

## Acceptance + steps

- [x] A project-owned workflow with the four generated lines gets the `${NAME:-default}` form on the next setup → `tests/test_tool_environment.py::test_project_owned_workflow_moves_to_runner_directories`.
- [x] The real setup plan writes the move for a project-owned workflow → `tests/test_tool_environment.py::test_setup_plan_includes_the_project_owned_workflow_move`.
- [x] A line with a custom directory is left alone → `tests/test_tool_environment.py::test_a_custom_tool_directory_stays_when_the_update_arrives` (same regex).
- [x] `hard-eng.yml` still migrates → `tests/test_tool_environment.py::test_older_workflow_keeps_runner_directories_after_the_update`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` bb1e34f: `tests/test_tool_environment.py` 4 passed. The new test failed before the change with `changes == {}` and the "Existing CI retained" message.
Execution: One builder; test, then the migration call, then the README line.

## Risks + recovery

A project that keeps a copy of the generated lines for another purpose gets the same safe default. Recovery: revert the commit.

## ux_reference

N/A — setup change with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed, 2085 tests passed, line coverage 91.34%. An earlier run failed `complexity` (`configure_ci` over the limit); the migration loop moved into its own function.
E2E: N/A — the test runs the real setup migration on a written workflow file.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
