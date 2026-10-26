# Require Canary on PRs into develop and main

Status: Complete

## Outcome + scope

A PR cannot merge into `develop` or `main` while a Canary new project fails. Non-goals: changing which files start Canary, the Mac release canary, or Canary's runtime.

## Repository context

Owners: `.github/workflows/canary.yml` (targets + new-project matrix); `hard-eng.gates.json` `shipping.checks`; GitHub branch protection for `main` (requires `hard-eng`) and `develop` (none).
Same cause: Canary was not required, so #404 merged while 4 Canary jobs failed (fixed by #405). The `new-project` matrix reports "skipped" when no installed file changed, which proves nothing, so a summary job must conclude every run. This branch was also started without a plan; the stop check caught it twice in this checkout, and no other branch is affected.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User approved on 2026-10-26: move `develop` to `main` (done, both at 4817e7fa) and make Canary required on both branches.

## Acceptance + steps

- [x] With no project listed, `canary` passes and says so → N/A — workflow shell step; run locally with LISTED=[] TARGETS=success PROJECTS=skipped: exit 0.
- [x] With projects listed, `canary` passes only when every new-project job passes, and fails when listing fails → N/A — workflow shell step; run locally: success → exit 0, failure → exit 1, targets failure → exit 1. This PR changes `hard-eng.gates.json`, so its own Canary run lists all targets as the remote proof.
- [x] `shipping.checks` names `canary`, so Hard Eng's ship check waits for it → N/A — configuration; the full gate validates the policy.

## Baseline + execution

Result: Passed
Evidence: Main CI `hard-eng.yml` run 40305300688 at 4817e7fa passed; Canary run 40304409305 on the same tree passed all 12 new-project jobs.
Execution: One builder, this session.

## Risks + recovery

- A PR that touches installed files now waits for the slowest Canary job (Flutter, about 5 minutes on #405) instead of `hard-eng` (about 3.5 minutes). Accepted by the user.
- macOS runner queues can delay that wait. Recovery: rerun the job; never bypass the check.

## ux_reference

N/A — CI configuration only; no visible UI.

## Verification

Result: Passed
Evidence: Local step runs above. Full gate `check --plan-stage Complete --base origin/develop`: 20 gates passed.
E2E: N/A — CI configuration; this PR's own Canary run proves the listed path, the local step run the other.
Delivery target: Merge
Delivery: Pending — this PR's Canary run passes with the new job; after merge, branch protection requires `hard-eng` and `canary` on `develop` and adds `canary` on `main`, read back with `gh api`.
