# Accept unchanged Complete plans that predate the UX Surface fields

Status: Complete

## Outcome + scope

Fix [#148](https://github.com/sgaabdu4/hard-eng/issues/148): `check --plan-stage Complete` rejects an unchanged Complete plan whose `## ux_reference` was written before the `Surface:`, `Before:`, `Proposed:`, `Capture:` and `Review:` fields existed. With no changed or unfinished plan, an explicit stage validates every plan, so one historical plan blocks the gate. Treat such a plan the way a missing `E2E:` line is already treated. Non-goals: relaxing any rule for a changed plan, a Ready plan, or a legacy plan that already declares `Surface:`.

## Repository context

Owner: `ux_proof` in `.hooks/plans.py`. `validate_plan` passes `legacy=True` for an unchanged Complete plan, and `readiness_errors` forwarded it only to `e2e_proof`, which returns early when a legacy verification has no `E2E:` line. `ux_proof` ignored it and always demanded the newer fields. Existing coverage: `test_unchanged_complete_plan_predates_e2e_rule` (legacy E2E) and `test_ready_requires_baseline_and_rendered_evidence`, which already proves a changed Complete or Ready plan without `Surface:` fails.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix this issue and open a PR; merging is not authorized.

## Acceptance + steps

- [x] An unchanged legacy Complete plan with `Result: Passed`, evidence and an image but no `Surface:` passes → new `test_unchanged_complete_plan_predates_ux_surface_rule`, red before the fix with the reported Surface error.
- [x] The same plan fails with the Surface error once edited → same test; a Ready or changed Complete plan without `Surface:` still fails → existing `test_ready_requires_baseline_and_rendered_evidence`.
- [x] An unchanged Complete plan that declares `Surface:` still gets the full rules (missing `Capture:` fails) → same new test.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: main at `ba19011`, CI run 35919600611 success. The new test on the unfixed code → 1 failed with "ux_reference: plan needs one 'Surface:' field, found 0".
Execution: Single session on `fix/legacy-ux-reference-plans`; pass `legacy` to `ux_proof` and return after the Passed and image checks when no `Surface:` line exists.

## Risks + recovery

A legacy plan keeps only the Passed, evidence and image checks until it is edited, which is the same allowance the E2E field already has. Revert the early return if a historical plan must meet the newer fields.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_plans.py` + `tests/test_planning_handoffs.py` → 75 passed. Ruff format and lint clean. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 801 tests.
E2E: N/A — plan validator change; the new test drives `validate_plans` against a committed Git fixture, the same path the CLI check uses.

Delivery target: PR
Delivery: Pending — PR checks green; merge left to the maintainer.
