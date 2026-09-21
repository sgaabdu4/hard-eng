# Run generated Python test gates in parallel

Status: Complete

## Outcome + scope

Setup makes a generated pytest tests gate run on every core: it adds `pytest-xdist` and `-n auto`. A new project gets this at install, and an existing project's older serial gate is upgraded the next time Hard Eng updates it. A gate that already sets `-n`, `--numprocesses`, `--dist` or `no:xdist` is left alone, so `-n 0` keeps a suite serial. When a parallel pytest gate fails, the check prints one line naming that opt-out. JavaScript and Dart gates are unchanged. No new file other than this plan.

## Repository context

Owners: `.hooks/project_setup.py` (generated gate commands), `setup.py` `configure_python` (runs for every Python package on install and on update, with the project's live gate configuration), `.hooks/reports.py` (test failure reporting) and `.agents/skills/he/references/gates.md`. The JavaScript template runs the project's own `test:coverage` script, and vitest and jest already use every core; `flutter test` and `dart test` run test files concurrently by default. Only the Python template ran serially. This repository's own gate gained `-n auto` in PR 133 and its suite went from 170 to 47 seconds locally.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the gates Hard Eng generates for other projects, to upgrade an existing older gate as well, and to make their CI fast. One function serves new and existing projects, because `configure_python` already runs in both paths. Only a command with the generated `uv run --with` shape is changed; a custom command is left alone because xdist may not be installable there. An update that changes `hard-eng.gates.json` already runs the project's checks in a candidate worktree and rolls back on failure, so a suite that cannot run in parallel keeps its current scaffold; the hint tells the user how to proceed. Merge awaits the user's go-ahead.

## Acceptance + steps

- [x] A new Python install has `pytest -n auto` with `pytest-xdist`; an older serial gate is upgraded on reinstall; a `-n 0` gate is preserved; the hint appears only for a failing parallel gate → `test_python_tests_run_in_parallel_unless_a_project_opts_out`.
- [x] Existing setup, runner and update tests pass unchanged.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 3c1df64, whose push CI run 35616913014 passed.
Execution: Single session on `feature/parallel-generated-tests`.

## Risks + recovery

A project whose tests share a database, port or fixed file fails under xdist. Its next Hard Eng update then fails its candidate check and rolls back until the project isolates that state or sets `-n 0`. A project whose pytest `addopts` sets `-n` is overridden by the command line's `-n auto`; only the gate command is inspected. Recovery is reverting this branch; an upgraded project reverts by editing its gate command.

## ux_reference

N/A — generated gate commands and one line of check output; no product appearance.

## Verification

Result: Passed
E2E: Passed — a scratch uv project was installed from this branch with the real `setup.py`. Its generated tests gate read `pytest -n auto` with `pytest-xdist`; the real `run_gate` ran it on 16 workers, 8 tests passed, and the coverage and JUnit reports were accepted. With a failing test added, the gate failed and printed the `-n 0` hint.
Evidence: The new test passes; `tests/test_setup.py`, `tests/test_runner.py` and `tests/test_updates.py` 178 passed before the hint was added. The full check result is recorded in the delivery line below.

Delivery target: PR
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks, 788 tests and 4 performance checks passed. A first run failed the types gate on untyped JSON in the new test; it now uses the typed config parser. PR CI and merge remain unverified.
