---
name: he-ship
description: Deliver one exact green Hard Eng snapshot through publish gates, authorized Git actions, and required CI.
---

# Hard Eng Ship

## Contract

- Input = `he` route + approved PLAN + `lifecycle_status=green` + exact green snapshot + `inspect` `handoff=ship` block (root, branch, plan, `BUILD.md`, prompt).
- Output = verified repository-policy delivery + `shipped`, or return to `he-build`.
- Owner = sync + snapshot continuity + publish gates + verified commit/push/PR/CI/merge + delivery receipt.
- Code/test/doc fixes = `he-build`; ship never patches a failing artifact.
- Decomposed epic ticket = this same contract, scoped to the ticket's `green_artifact`; epic ships only after every ticket `shipped` + `T-int` `green` = workflow.md `Ticket Ship` / `Epic Closure`.
- Load [workflow.md](references/workflow.md) before shipping or resume.

## Invariants

- Commit/push/PR/merge/publish + named deploy + recoverable live data/schema work = continue once target/effect are known; protected approval is not required.
- Stop boundary = permanent data/file/schema deletion + uncommitted-work loss + force push/remote history loss + secret exposure → fresh exact approval.
- Fresh exact approval receipt = one matching irreversible destructive call only; changed input + repeat require another stop.
- Unrequested irreversible destructive delivery action = state exact target + permanent effect → ask once.
- Ready-to-build approval ≠ irreversible destructive authorization; missing material delivery choice = one decision.
- Explicit terminal delivery outcome persists across recoverable build/CI failures, retries, and turn boundaries; one failed attempt never narrows the goal.
- Missing project gate manifest/family = invalid green snapshot → `he-build` + `deterministic-checks` `gate-migration`; Ship never wires it.
- Sync/content/CI change → `he-build` final loop; green evidence becomes stale.
- `assert-green` = working artifact at Ship entry + current mutation receipt covering every source file changed since the approval base (`mutation=missing` → `he-build` records it); `assert-green --delivered-head` = post-commit HEAD/index/worktree exactness before push; either failure returns to `he-build`.
- Read `features/<slug>/BUILD.md` before delivery; it is the human summary of every slice's edge, green, review, and verify records.
- Publish gate = `deterministic-checks` `publish` PASS on exact intended diff.
- Delivery SHA = remote product artifact identity; later local lifecycle-state bytes are not part of that artifact.
- Force push without exact protected approval + bypassed hook/check + hidden path + fabricated remote result = forbidden.
- Rollback + observability + protected-boundary evidence = retained through delivery.
- Process learning = record + defer without blocking unless continued delivery risks a protected boundary.
- Stop = user override OR protected-boundary stop OR exact external authority blocker; deterministic product/tool failure → `he-build` + resume Ship.

## Complete

- Delivered artifact = exact green reviewed snapshot.
- Remote ref/PR/merge + required CI = verified.
- Repository delivery contract = satisfied.
- `he` local checkpoint = `lifecycle_status=shipped` + delivery SHA/URL/result in `next_action`; it does not rewrite delivered artifact identity or imply another commit.
