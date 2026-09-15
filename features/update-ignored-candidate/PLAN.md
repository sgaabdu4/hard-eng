# Verify managed updates despite local ignore rules

Status: Complete

## Outcome + scope

Allow an isolated update candidate to stage its explicitly planned managed files even when repository-local ignore rules match newly installed paths. Preserve the caller's index, checkout, ignores and unrelated files.

## Repository context

The existing verify_candidate function creates and stages a disposable Git worktree before running candidate checks. Its test_candidate_uses_remote_task_plan_scope fixture already checks caller index and worktree preservation. Extend those owners only.

## Decisions + authorization

Blockers: None
The user authorized canonical installer repairs and delivery. Reuse the existing candidate verifier and its regression fixture. Force staging applies only to the already validated names in the disposable candidate; no broad staging or ignore-file edits. This plan records the existing required verification and delivery state; no runtime file or dependency is added.

## Baseline + execution

Result: Passed
Evidence: Main b77e811 passed source and hosted gates. A detached candidate shares repository-local info/exclude rules; plain git add rejects a newly managed path matched by such a rule. The regression reproduces that condition using a synthetic managed file.

## Acceptance + steps

- [x] Explicit managed candidate paths can be staged despite local ignore rules.
- [x] The original checkout and staged user work remain unchanged.
- [x] Existing update tests pass, including candidate success and failure paths.
- [x] Required source checks pass.

## Risks + recovery

The force option must remain confined to explicit candidate paths; consumer staging and ignore rules are unchanged. Actual installation remains guarded by the existing candidate checks and conflict validation.

## ux_reference

N/A — installer behavior changes no product UI.

## Verification

Result: Passed
Evidence: All 35 update tests passed using real isolated Git fixtures; the regression includes the ignored managed path and verifies the caller checkout and index remain unchanged. The full run passed all 660 source tests, four performance tests, type, security and dependency checks. Its initial statement-limit finding was fixed by simplifying the same fixture; targeted Ruff and whitespace checks then passed. Native pre-push rechecks the committed revision before publication.
E2E: Passed — the candidate regression exercises real Git worktrees, shared ignore configuration, staging and cleanup.

Delivery target: Merge
Delivery: Pending — PR, current required CI and merged revision verification remain required.
