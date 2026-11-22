# Remove partial git subprocess from client-report check script

Status: Complete

## Outcome + scope

Find the repository root in `.agents/skills/client-report/scripts/check_report.py` without invoking a `git` subprocess, so Python repositories with strict Ruff subprocess rules (`S603`, `S607`) pass lint after installing Hard Eng. Out of scope: report HTML parsing, template rules, and other skills.

## Sources + coverage

Sources: N/A — bug found during Hard Eng installation in a Python repository with Ruff `S603` and `S607` enabled.
Deliverables: None

## Repository context

Owners: `.agents/skills/client-report/scripts/check_report.py` (`saved_template`) and `tests/test_client_report.py`.
Same cause: `saved_template()` called `subprocess.run(["git", "rev-parse", "--show-toplevel"], ...)`, which triggers Ruff `S607` (partial executable path) in installed Python repositories that scan `.agents/skills/`. Walking `Path.cwd().resolve()` ancestors for `.git` removes `subprocess` entirely.
Single source: repository-root lookup lives once in `saved_template()`.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Maintainer autonomous rollout approval on 2026-11-22 to fix defects blocking Hard Eng rollout and deliver through `develop`.

## Acceptance + steps

- [x] `saved_template()` finds the repository root from inside a git checkout, validates `.git` metadata (rejecting directories outside a checkout, broken `.git` worktree pointers, and paths inside `.git/`), and runs without `subprocess` → `tests/test_client_report.py::test_the_command_finds_the_template_from_the_git_top_level`
- [x] `.agents/skills/client-report/scripts/check_report.py` imports no `subprocess` module and passes `ruff check --select S603,S607` → `tests/test_client_report.py::test_check_report_script_passes_strict_ruff_subprocess_rules`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`a2a51c09`), `ruff check --select S603,S607 .agents/skills/client-report/scripts/check_report.py` failed with `S607 Starting a process with a partial executable path` on line 122. After removing `subprocess` and resolving `.git` from parent directories, all 16 tests in `tests/test_client_report.py` and `ruff check --select S603,S607` pass.
Execution: One commit for the script fix and regression test, plus this plan.

## Risks + recovery

Risk: a checkout using `GIT_DIR`/`GIT_WORK_TREE` outside the working tree or a bare repository lacks a local `.git` entry, returning `None`; `--template` remains available as an explicit override. Recovery: revert the commit.

## ux_reference

N/A — CLI helper script only; no UI changes.

## Verification

Result: Passed
Evidence: `pytest tests/test_client_report.py` passed 16/16 tests; `ruff check` and `ruff format --check` passed on both changed files; `ruff check --select S603,S607 .agents/skills/client-report/scripts/check_report.py` exited 0.
E2E: N/A — CLI script tested end to end via real subprocess invocation in `tests/test_client_report.py::test_the_command_finds_the_template_from_the_git_top_level`.
Real service: N/A — local filesystem only; no outside service calls.
Retro: Escaped base-branch bug (`S607` in installed skill script) -> added regression test `tests/test_client_report.py::test_check_report_script_passes_strict_ruff_subprocess_rules`.

Delivery target: Merge
Delivery: Pending — required remote proof.
