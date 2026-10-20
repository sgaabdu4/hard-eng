# Cut gate output

Status: Complete

## Outcome + scope

When the stop hook cuts a failing gate's output to its limit, the summary now says so and tells the agent to rerun the check for the full log. Before, the agent could not tell a cut log from a whole one. Non-goals: a different limit.

## Repository context

Owner: `failure_summary` in `.hooks/agent_hooks.py`, which builds the stop hook's failure reason from the quick check log. Its three return paths each cut to `GATE_OUTPUT_LIMIT`.
Same cause: one cause, all three paths cut silently; one helper now cuts and marks.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, with every decision made by the agent.

## Acceptance + steps

- [x] A cut summary says it is cut → `tests/test_stop_checks.py::test_failure_reason_lists_failed_gates_and_starts_at_the_first_error`.

## Baseline + execution

Result: Passed
Evidence: `develop` b359445: the new assertion failed there.
Execution: One builder; failing assertion, then the helper.

## Risks + recovery

None beyond one extra line in a cut summary.

## ux_reference

N/A — hook text with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1817 passed, the same 8 environment failures as `develop`; `tests/test_stop_checks.py` 16 passed. Ruff, Pyrefly (0 errors), Vulture and jscpd (0 clones) pass.
E2E: N/A — the test runs the real stop hook against a real check script in a real Git repository.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
