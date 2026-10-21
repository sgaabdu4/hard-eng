# Wait two days before installing new tool releases

Status: Complete

## Outcome + scope

Hard Eng installs the newest version of its npm and mise-managed tools only after a two-day wait. Non-goals: the mise launcher install, and project dependency settings.

## Repository context

Owners: `.hooks/tool_setup.py` (`provision_batch`, `provision_latest`); tests in `tests/test_tool_execution.py` and `tests/test_runner.py`.
Same cause: N/A — the only other install paths are `install_launcher` (mise itself, out of scope) and project setup, which already reads the project's own release-age setting.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-21 to add at least a two-day wait after a newly published tool release broke checks in several projects.

## Acceptance + steps

- [x] An npm tool install waits at least 172800 seconds before taking a new release → `tests/test_tool_execution.py::test_native_tools_install_before_reading_environment` (checks the Bun release-age flag in the install command).
- [x] A mise install waits two days → `tests/test_runner.py::test_wrapped_actionlint_and_decimate_use_latest_packages` (checks `MISE_MINIMUM_RELEASE_AGE=2d` on every mise command).
- [x] Existing behavior still holds: install commands still use the Bun package manager → same test in `tests/test_runner.py`.

## Baseline + execution

Result: Passed
Evidence: Reused the passed `hard-eng.yml` CI run 39054549201 on main at fbbb0312 (found with `gh run list -b main --workflow hard-eng.yml`; conclusion success). This branch point's code is unchanged in the baseline.
Execution: One builder, this session.

## Risks + recovery

- Bun flag overrides a longer user release-age limit in `~/.bunfig.toml`. Two days still meets the requested minimum; a user can raise it later.
- A release that is pulled inside two days still reaches the gate. Recovery: pin the tool with a reviewed version and report the release.
- The Biome 2.6 format repair is not on main. From 2026-10-23 the wait allows Biome 2.6.2 again, so main fails format unless that repair lands first.

## ux_reference

N/A — no visible UI change; command-line installer only.

## Verification

Result: Passed
Evidence: Focused tests `tests/test_tool_execution.py`, `tests/test_runner.py`, `tests/test_tool_setup.py`: 200 passed. Full Ready-stage `check --plan-stage Ready --base origin/main`: all 19 gates passed, tests 189s. The install log shows `npm:@biomejs/biome@2.5.15` installed under `--minimum-release-age=172800`.
Delivery target: Merge
Delivery: Pending — PR merged to main; main CI install step shows a release at least two days old.
E2E: N/A — installer behavior has no user journey; the install command assertions prove the wait.
