# Failed gate recap

Status: Complete

## Outcome + scope

A failing `check` names every failed gate in its last line, for example `Hard Eng: verification failed in ./tests, ./types; the next stage is blocked.`, so an agent does not rerun the suite to find which gate failed. Non-goals: failing test names, and changing gate output order.

## Repository context

Owners: `run_gate` in `.hooks/hard-eng.py` knows each gate's key and result; `run_gates` starts each run; `report_stage` in `.hooks/plans.py` prints the last line. Parallel gates interleave output, so the `FAIL` lines can sit hundreds of lines up. `hard-eng.py` stays at 999 lines: the `pre-push` subcommand now shares the hook-name branch, and one help string got shorter.
Same cause: N/A — one missing summary, not a fix of a repeated defect.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, gate bugs first, with every decision made by the agent. Decided: the recap joins the existing last line instead of adding one, so tools that match `Hard Eng: verification failed` keep working.

## Acceptance + steps

- [x] A failing check names the failed gate in its last line, and a later passing check names none → `tests/test_runner.py::test_command_failure_survives_later_pass`.
- [x] `hard-eng.py pre-push` still runs the pre-push check → `tests/test_runner.py::test_pre_push_tests_committed_code`.

## Baseline + execution

Result: Passed
Evidence: `develop` 77a41b4: the updated test failed, because the last line named no gate; the full suite had only the 8 known environment failures.
Execution: One builder; failing test, then the recap.

## Risks + recovery

A gate key holds the package path and gate name only; a gate that fails through a scanner report shows the same key.

## ux_reference

N/A — command-line output change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1801 passed, the same 8 environment failures as `develop`. Ruff, Pyrefly, Vulture, jscpd and deptry pass; `hard-eng.py` 999 lines, `plans.py` 1000 lines. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the runner test runs the real `check` with real gate commands.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
