# A runner's own tool and cache directories win in the generated workflow

Status: Draft

## Outcome + scope

The generated `hard-eng.yml` sets `MISE_DATA_DIR`, `MISE_CACHE_DIR`, `MISE_STATE_DIR` and `BUN_INSTALL_CACHE_DIR` under the runner's temporary folder only when the runner has not already exported them. On GitHub-hosted runners nothing changes. A self-hosted runner that ships a tool set or keeps caches between jobs reuses them instead of downloading every tool again. Non-goals: the paths themselves, the Python tool setup.

## Repository context

Owners: the impact step of `.github/workflows/hard-eng.yml` (copied whole into new installs) and `migrate_tool_environment` in `.hooks/ci_setup.py`.
Same cause: one cause, the step wrote the four values to `GITHUB_ENV` unconditionally, so every later step in the job used throwaway paths. `provision_batch` in `.hooks/tool_setup.py` already keeps a value from the environment (`setdefault`), and `tests/test_ci_setup.py::test_native_tool_bootstrap_preserves_ci_sdk_executables` covers it; no other file writes these variables.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-10-29 for this follow-up as a pull request into `develop`, without a merge. Decided: the value is `${NAME:-default}`, so an empty variable also gets the default, and the migration rewrites only the four generated lines whose value is the generated temp path.

## Acceptance + steps

- [ ] With no variable set, the impact step exports today's four temp paths → `tests/test_tool_environment.py::test_unset_directories_use_the_runner_temp_paths`.
- [ ] A variable the runner already exports is kept, and the others still get the temp path → `tests/test_tool_environment.py::test_directories_the_runner_exports_are_kept`.
- [ ] An install generated before this change gets the same lines on the next update, once → `tests/test_tool_environment.py::test_older_workflow_keeps_runner_directories_after_the_update`.
- [ ] A line with a custom directory is left alone → `tests/test_tool_environment.py::test_a_custom_tool_directory_stays_when_the_update_arrives`.
- [ ] A generated workflow carries the new lines → `tests/test_ci_setup.py::test_generated_ci_timeout`.

## Baseline + execution

Result: Pending
Evidence: Pending.
Execution: One builder; template line, then the migration, then the tests.

## Risks + recovery

A runner that exports a directory the job user cannot write fails the install step; unset the variable on that runner. Recovery: revert the four lines.

## ux_reference

N/A — workflow and setup change with no visual surface.

## Verification

Result: Pending
Evidence: Pending the full check.
E2E: N/A — the tests run the generated step in a real shell and the real setup migration on written workflow files; reuse of a pre-installed tool set on a self-hosted runner is not provable here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
