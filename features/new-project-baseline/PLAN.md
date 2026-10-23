# New projects start with a passing check

Status: Complete

## Outcome + scope

The release canary on `develop` be31518 gave agent sessions new projects whose first full check already failed. Agents treated those failures as old and out of scope, then stopped. This plan makes each new project pass its first check:

1. A new Python project had only `uv init` output: no tests, so coverage and the performance suite failed. `setup.sh --new python` now runs `uv init --app` and `uv lock`, then adds a starter with a tested `main.py` and a performance test. The release canary creates its greenfield target with `--new python`.
2. In the brownfield target, uv printed a warning when an outer `VIRTUAL_ENV` pointed at another environment. The debt match counted that warning as a new finding, so the `dependencies` gate failed. The warning is now a runner line, like the other uv and mise noise.

Non-goals: failures in installed projects themselves.

## Repository context

Owners: `new_project.py` (`SCAFFOLDS`, `create`), `.agents/starters/python/`, `setup.py` (`--new` choices), `README.md`, `.hooks/debt.py` (`RUNNER_LINES`), `release_canary.py` (`install_new`). Tests in `tests/test_new_project.py` and `tests/test_debt.py`.
Same cause: the scaffold stacks (flutter, nextjs, opennext, vite) already add starter tests and a performance suite; only Python lacked one. Other uv warnings in `RUNNER_LINES` cover `UV_` variables only.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: On 2026-10-23 the user chose "Fix first, then release" for the agent stops in the canary.
Decided: ignore the uv warning in the debt match, not strip `VIRTUAL_ENV` from every gate, because uv already ignores a mismatched `VIRTUAL_ENV` and other tools may need it. Python joins the `--new` stacks so the canary and users create the same starting project.

## Acceptance + steps

- [x] A new Python project is locked and has starter tests and a performance suite → `tests/test_new_project.py::test_python_locks_the_scaffold_and_adds_tested_starter_code`.
- [x] A mismatched `VIRTUAL_ENV` warning is not a debt finding → `tests/test_debt.py::test_a_mismatched_virtual_env_warning_is_not_a_finding`.
- [x] The canary greenfield target uses `--new python` → N/A — reason: the release canary's greenfield run proves it on the maintainer's Mac.

## Baseline + execution

Result: Passed
Evidence: In the cloud, `setup.sh SOURCE --new python` and then a full check exits 0 with a clean tree. In a copy of the brownfield target, the full check fails only when `VIRTUAL_ENV` points at another environment.
Execution: One builder, this session.

## Risks + recovery

Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container; PR CI runs it with every toolchain; the release canary reruns on the maintainer's Mac before main.
E2E: N/A — no user journey; the canary is the end-to-end run.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
