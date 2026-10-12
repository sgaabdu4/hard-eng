# Run pre-push mutation testing to completion

Status: Ready

## Outcome + scope

Pre-push mutation testing no longer stops after 180 seconds. It reports every changed production line and still never blocks the push. Non-goals: the on-demand `mutation --seconds` option, mutation adapters, the pre-push check budget.

## Repository context

Owner: `pre_push` in `.hooks/ship_actions.py` passed `--seconds 180` to `mutation`. `tests/test_ship_actions.py` asserted those arguments. `README.md` and `.agents/skills/he/references/workflow.md` described the limit. Mutation time is already excluded from the `pre_push_seconds` budget warning.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to remove the 3-minute local mutation limit, run mutation fully and fix the results.

## Acceptance + steps

- [x] Pre-push runs `mutation --base <base> --in-place` with no time limit.
- [x] The existing pre-push test asserts the new arguments.
- [x] README and workflow guidance describe the full run.
- [ ] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: All 40 `tests/test_ship_actions.py` cases pass after the change.
Execution: One builder; one owner change.

## Risks + recovery

Pushes with many changed lines take longer, because mutation now runs to completion. It still cannot block a push. Recovery: restore a limit if push time becomes a problem.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Pending
Evidence: Pending full gate.
E2E: N/A — covered by the pre-push test with a stubbed runner.

Delivery target: Merge
Delivery: Pending
