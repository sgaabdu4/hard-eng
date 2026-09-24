# Keep unchanged legacy Complete plans passing the UX rules

Status: Draft

## Outcome + scope

Fix [#148](https://github.com/sgaabdu4/hard-eng/issues/148): an unchanged Complete plan whose `ux_reference` predates the `Surface:` field passes `check --plan-stage Complete` under the rules it was written for (Passed result, actual evidence, a Markdown image). Editing it, or adding `Surface:`, applies the full current rules. Non-goals: relaxing the rules for changed, Draft or Ready plans.

## Repository context

Owners: `ux_proof` and `readiness_errors` in `.hooks/plans.py`. `validate_plan` passes `legacy=True` for unchanged Complete plans, but only `e2e_proof` uses it. The older rules are those before a2e6c8f: `proof(..., {"Passed"})` plus one Markdown image.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix all open Hard Eng issues, check edge cases, and merge to main through a PR.

## Acceptance + steps

- [ ] Unchanged legacy Complete plan without `Surface:` → validates; the same plan once edited → fails naming `Surface`; `tests/test_plans.py` proves both.
- [ ] Legacy plan without `Surface:` and without an image, or with a non-Passed result → still fails.
- [ ] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Pending
Evidence: Pending — full gate on unchanged `ba19011`.
Execution: One builder; pass `legacy` to `ux_proof` and stop after the older rules when `Surface:` is absent.

## Risks + recovery

A legacy exemption could let a weak plan through; it applies only to unchanged Complete plans and still enforces the older rules. Revert the early return if a changed plan passes without `Surface:`.

## ux_reference

N/A — no visual surface.

## Verification

Result: Pending
Evidence: Pending — targeted tests and full gate.
E2E: N/A — plan validation change; the CLI check on a legacy plan exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
