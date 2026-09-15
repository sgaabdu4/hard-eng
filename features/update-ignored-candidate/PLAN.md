# Verify managed updates despite local ignore rules

Status: Complete

## Outcome + scope

Allow candidate verification and the resulting update commit to stage explicitly planned managed files even when repository-local ignore rules match newly installed paths. Preserve unrelated staged and working files and the caller's ignore rules.

## Repository context

The existing verify_candidate function stages a disposable Git worktree before running candidate checks; commit_update then stages the approved managed paths in the target. Existing update fixtures check both phases and preservation of unrelated staged and working files. Extend those owners only.

## Decisions + authorization

Blockers: None
The user authorized canonical installer repairs and delivery. Reuse the existing verifier, scoped update commit and their regression fixtures. Force staging applies only to the already validated managed names in each phase; no broad staging or ignore-file edits. This plan records the existing required verification and delivery state; no runtime file or dependency is added.

## Baseline + execution

Result: Passed
Evidence: Main b77e811 passed source and hosted gates. A detached candidate shares repository-local info/exclude rules; plain git add rejects a newly managed path matched by such a rule. The regression reproduces that condition using a synthetic managed file.

## Acceptance + steps

- [x] Explicit managed candidate paths can be staged despite local ignore rules.
- [x] Candidate verification preserves the original checkout and staged user work.
- [x] Actual updates commit the ignored managed additions and preserve unrelated user work.
- [x] Existing update tests pass, including candidate success and failure paths.
- [x] Required source checks pass.

## Risks + recovery

The force option must remain confined to explicit managed paths; unrelated staging and ignore rules are unchanged. Actual installation remains guarded by the existing candidate checks and conflict validation.

## ux_reference

N/A — installer behavior changes no product UI.

## Verification

Result: Passed
Evidence: All 35 initial update tests passed using real isolated Git fixtures. The full source run passed 660 tests, four performance tests, types, security and dependency checks; an initial statement-limit finding was fixed within the same fixture. Integration review then reproduced a second failure: the candidate passed, but the actual update commit rejected a newly added ignored managed reference. The paired scoped-staging repair passes that real update regression and preserves unrelated staged and working files. Ruff and whitespace checks pass. A prior native pre-push passed functional checks but exceeded the unchanged 180-second budget; committed-revision verification must pass that budget before publication.
E2E: Passed — real Git worktrees, shared ignore configuration, candidate staging, actual scoped update commits and cleanup; regression failed before the paired repair and passed afterward.

Delivery target: Merge
Delivery: Pending — PR, current required CI and merged revision verification remain required.
