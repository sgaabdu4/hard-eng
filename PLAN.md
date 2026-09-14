# Update generated action pins

Status: Complete

## Outcome + scope

Upgrade only actions/checkout to v7.0.1 and pnpm/setup to v2.1.0 in the existing workflow, which also supplies fresh project generation.

## Repository context

.github/workflows/hard-eng.yml is the source template consumed by configure_ci in .hooks/project_setup.py. Reuse tests/test_setup.py's installer test; no new files or machinery.

## Decisions + authorization

Blockers: None

The authorized source repair includes testing, PR, merge and main verification. One builder uses an isolated worktree to preserve unrelated unfinished work. Both requested release tags resolve through their official GitHub repositories to the supplied commit pins.

## Acceptance + steps

- [x] Source workflow and newly generated workflow use both requested commit pins.
- [x] Existing installer checks pass; final Complete gate follows before shipping.

## Baseline + execution

Result: Passed
Evidence: Unchanged source7e282a66297f7a78b37c29bf31b17a8c38bc4f28 passed473 regression tests, four performance tests and all17 gates. Main CI34823711560 passed. Matching local Ready gate passed before this isolated change; only planning text differs.

## Risks + recovery

Major checkout action upgrade requires hosted CI verification. Existing target workflows are intentionally preserved by configure_ci; this change updates source and fresh generation only. No unrelated dependency upgrades.

## ux_reference

N/A — CI configuration has no visual application surface.

## Verification

Result: Passed
Evidence: Official GitHub release refs verified. All61 existing installer tests passed. A direct configure_ci invocation independently verified both exact pins in fresh generated output. The isolated Ready gate passed before edits. Diff review confirms only the two workflow pins, the existing installer assertion and this plan changed. Final Complete gate follows before shipping.

Delivery target: Merge
Final Complete gate passed all17 checks,473 regression tests and four performance tests. Ready for ship — local implementation and verification complete; delivery not performed.

PR CI34826029561 passed, including both upgraded action steps. Explicit pre-push verification failed because its temporary worktree does not initialize source skill submodules; the initialized source Complete gate passed. This separate source pre-push limitation is not repaired by this two-pin change.

Delivery: Pending — current PR CI, merge, exact main CI and native delivered verification.
