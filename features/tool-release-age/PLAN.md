# Wait two days before installing new tool releases

Status: Complete

## Outcome + scope

Hard Eng installs the newest version of its npm and mise-managed tools only after a two-day wait. Non-goals: the mise launcher install, and project dependency settings.

## Repository context

Owners: `.hooks/tool_setup.py` (`provision_batch`, `provision_latest`); `.github/workflows/hard-eng.yml` (CI bootstrap); `.hooks/ci_setup.py` (`configure_ci` migrates existing consumer workflows); tests in `tests/test_tool_execution.py` and `tests/test_runner.py`.
Same cause: N/A — the only other install paths are `install_launcher` (mise itself, out of scope) and project setup, which already reads the project's own release-age setting.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-21 to add at least a two-day wait after a newly published tool release broke checks in several projects.

## Acceptance + steps

- [x] An npm tool install waits at least 172800 seconds before taking a new release → `tests/test_tool_execution.py::test_native_tools_install_before_reading_environment` (checks the Bun release-age flag in the install command).
- [x] A mise install waits two days → `tests/test_runner.py::test_wrapped_actionlint_and_decimate_use_latest_packages` (checks `MISE_MINIMUM_RELEASE_AGE=2d` on every mise command).
- [x] CI bootstrap installs uv and SDK tools with the same wait → N/A — workflow setting only: the `.github/workflows/hard-eng.yml` job env sets `MISE_MINIMUM_RELEASE_AGE: 2d` (read in the diff; actionlint and zizmor pass). The PR's CI install log is the remote proof under Delivery.
- [x] An existing project's generated workflow moves from `0s` to `2d` on its next Hard Eng update → `tests/test_ci_setup.py::test_existing_workflow_gets_the_two_day_release_wait` (failed before the migration, passes after).
- [x] A workflow generated before the setting moved to job level also changes its step-level `0s`, which would otherwise override the job value → `tests/test_ci_setup.py::test_existing_workflow_gets_the_two_day_release_wait` with a step-level line (failed before, passes after).
- [x] Existing behavior still holds: install commands still use the Bun package manager → `tests/test_runner.py::test_wrapped_actionlint_and_decimate_use_latest_packages`.
- [x] The shipped Biome config loads on the Biome the two-day wait selects (2.5.15 until 23 October) and on 2.6.2: the SKILL.md override turns off the formatter, not the 2.6-only `markdown` key → N/A — config only; `biome ci` and the focused-tests lint on `.agents/skills` pass on both 2.5.15 and 2.6.2, and develop CI failed with "unknown key `markdown`" before.

## Baseline + execution

Result: Passed
Evidence: Reused the passed `hard-eng.yml` CI run 39054549201 on main at fbbb0312 (found with `gh run list -b main --workflow hard-eng.yml`; conclusion success). This branch point's code is unchanged in the baseline.
Execution: One builder, this session.

## Risks + recovery

- Bun flag overrides a longer user release-age limit in `~/.bunfig.toml`. Two days still meets the requested minimum; a user can raise it later.
- A release that is pulled inside two days still reaches the gate. Recovery: pin the tool with a reviewed version and report the release.
- CI runtime installs (uv, Python, Node, Dart) now also wait two days, so a runtime security patch reaches CI two days later. Accepted: CI is build-time; production runtimes do not come from this path.
- A release younger than two days that a checkout installed before this change keeps running there, because mise's `@latest` follows its link to the newest installed copy. Nothing installs such a copy after this change, so the gap closes within two days of that release. An exact-version lookup would close it at the cost of one extra `mise latest` call per tool on every check; not done.
- The mise launcher itself still installs its newest release (out of scope).
- The Biome 2.6 format repair is not on main. From 2026-10-23 the wait allows Biome 2.6.2 again, so main fails format unless that repair lands first.

## ux_reference

N/A — no visible UI change; command-line installer only.

## Verification

Result: Passed
Evidence: Focused tests `tests/test_tool_execution.py`, `tests/test_runner.py`, `tests/test_tool_setup.py`: 200 passed. Full Ready-stage `check --plan-stage Ready --base origin/main`: all 19 gates passed, tests 189s. The install log shows `npm:@biomejs/biome@2.5.15` installed under `--minimum-release-age=172800`. Independent review (codex) at f1387383 found two items: the CI bootstrap still used `0s` (fixed), and an already-installed young copy still runs through mise's `@latest` link (reproduced; not fixed, see Risks). A second review at b6924263 found that existing consumer workflows kept `0s` (fixed with a migration). A third review at 08332e3a found that workflows from before the setting moved to job level keep a step-level `0s` (fixed: every generated `0s` line now moves to `2d`). Complete-stage `check --plan-stage Complete --base origin/main` after the fix: all 19 gates passed; Biome 2.5.15 in use.
Delivery target: Merge
Delivery: Pending — PR merged to main; main CI install step shows a release at least two days old.
E2E: N/A — installer behavior has no user journey; the install command assertions prove the wait.
