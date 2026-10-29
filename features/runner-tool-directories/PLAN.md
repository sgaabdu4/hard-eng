# A runner's own tool and cache directories win in the generated workflow

Status: Complete

## Outcome + scope

The generated `hard-eng.yml` sets `MISE_DATA_DIR`, `MISE_CACHE_DIR`, `MISE_STATE_DIR` and `BUN_INSTALL_CACHE_DIR` under the runner's temporary folder only when the runner has not already exported them. On GitHub-hosted runners nothing changes. A self-hosted runner that ships a tool set or keeps caches between jobs reuses them instead of downloading every tool again. The same branch also raises the pytest floor to 9.2.0, because the freshness gate fails on `develop` itself once a release is two days old (pytest 9.2.0, released 2026-10-27). Non-goals: the paths themselves, the Python tool setup.

## Repository context

Owners: the impact step of `.github/workflows/hard-eng.yml` (copied whole into new installs) and `migrate_tool_environment` in `.hooks/ci_setup.py`.
Same cause: one cause, the step wrote the four values to `GITHUB_ENV` unconditionally, so every later step in the job used throwaway paths. `provision_batch` in `.hooks/tool_setup.py` already keeps a value from the environment (`setdefault`), and `tests/test_ci_setup.py::test_native_tool_bootstrap_preserves_ci_sdk_executables` covers it; no other file writes these variables.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-10-29 for this follow-up as a pull request into `develop`, without a merge. Decided: the pytest floor change is its own commit in this pull request, not a separate one, because one pull request carries all tasks in hand; and the value is `${NAME:-default}`, so an empty variable also gets the default, and the migration rewrites only the four generated lines whose value is the generated temp path.

## Acceptance + steps

- [x] With no variable set, the impact step exports today's four temp paths → `tests/test_tool_environment.py::test_unset_directories_use_the_runner_temp_paths`.
- [x] A variable the runner already exports is kept, and the others still get the temp path → `tests/test_tool_environment.py::test_directories_the_runner_exports_are_kept`.
- [x] An install generated before this change gets the same lines on the next update, once → `tests/test_tool_environment.py::test_older_workflow_keeps_runner_directories_after_the_update`.
- [x] A line with a custom directory is left alone → `tests/test_tool_environment.py::test_a_custom_tool_directory_stays_when_the_update_arrives`.
- [x] A generated workflow carries the new lines → `tests/test_ci_setup.py::test_generated_ci_timeout`.
- [x] The freshness gate passes on the branch → N/A — the gate is part of `check`, which reports `PASS freshness` once the floor names 9.2.0.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 383b791: the full check passed 19 of 20 gates and 2009 tests; `freshness` failed on `develop` itself (pytest 9.1.1 → 9.2.0). Run against the old template and `ci_setup.py`, the preset-directory test and the migration test failed; the other two passed because unset behaviour is unchanged.
Execution: One builder; template line, then the migration, then the tests.

## Risks + recovery

A runner that exports a directory the job user cannot write fails the install step; unset the variable on that runner. Recovery: revert the four lines.

## ux_reference

N/A — workflow and setup change with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed and 2009 tests passed. Actionlint and Zizmor (auditor persona) report nothing on the changed template.
E2E: N/A — the tests run the generated step in a real shell and the real setup migration on written workflow files; reuse of a pre-installed tool set on a self-hosted runner is not provable here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
