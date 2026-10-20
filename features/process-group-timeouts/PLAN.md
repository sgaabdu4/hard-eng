# Process group timeouts

Status: Complete

## Outcome + scope

A timeout in `challenge`, a gate command or a live agent case stops every process the command started, not only the direct child. Non-goals: changing timeout values, the Stop hook, `ship_actions`, `update_runner` and the release canary, which already stop their groups.

## Repository context

Owners: `review` in `.hooks/challenge.py`, `run_gate_command` in `.hooks/gitleaks_scan.py` and `stream` in `tests/agent_checks.py` used `subprocess.run(timeout=…)`, which kills only the direct child. `run` in `.hooks/mutation.py` already ran its tool in its own group; `.hooks/process_group.py` now holds that pattern once and `mutation.run` uses it. `challenge.md` tells agents how to wait for a review that outlives a foreground tool call.
Same cause: one cause, `subprocess.run` with a timeout leaves grandchildren alive; all three call sites now use the one group runner.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, gate bugs first, with every decision made by the agent. Decided: one shared runner instead of a fifth copy of the pattern.

## Acceptance + steps

- [x] A timed-out reviewer leaves no process behind → `tests/test_challenge.py::test_a_timed_out_reviewer_leaves_no_process_behind`.
- [x] A timed-out gate leaves no process behind → `tests/test_current_files_gitleaks.py::test_a_timed_out_gate_leaves_no_process_behind`.
- [x] A timed-out live agent case leaves no process behind → `tests/test_agent_checks.py::test_a_timed_out_agent_leaves_no_process_behind`.
- [x] Mutation testing still stops at its cap and leaves no process → `tests/test_mutation.py::test_a_capped_tool_raises_capped_and_leaves_no_process_behind`.

## Baseline + execution

Result: Passed
Evidence: `develop` 9c61244: the three new tests failed with the child still running; the full suite had only the 8 known environment failures.
Execution: One builder; failing tests, then the shared runner and its call sites.

## Risks + recovery

A gate that starts a long-lived helper without its own session loses that helper on timeout only; a normal exit keeps the old behavior.

## ux_reference

N/A — process handling with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1800 passed, the same 8 environment failures as `develop`. Ruff format, lint, complexity and annotations, Pyrefly (0 diagnostics), Vulture and jscpd pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — each test runs the real call site against a real process tree.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
