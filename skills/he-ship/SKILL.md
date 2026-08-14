---
name: he-ship
description: Deliver one exact green Hard Eng snapshot through publish gates, authorized Git actions, and required CI.
---

# Hard Eng Ship

## Contract

- Input = `he` route + approved PLAN + `lifecycle_status=green` + exact green snapshot.
- Output = verified repository-policy delivery + `shipped`, or return to `he-build`.
- Owner = sync + snapshot continuity + publish gates + authorized commit/push/PR/CI/merge + delivery receipt.
- Code/test/doc fixes = `he-build`; ship never patches a failing artifact.
- Load [workflow.md](references/workflow.md) before shipping or resume.

## Invariants

- Exact task authorization for commit/push/PR/merge/publish = continue without another approval while target/effect stay unchanged.
- Valid autonomous receipt = commit/push/PR/merge/CI + named deploy + additive live data/schema continue without another approval.
- Autonomous stop boundary = destructive/data-loss + force/history rewrite + secret exposure + payment/material spend + account/permission + protected live-write retry + changed target/effect → fresh exact approval.
- Fresh exact approval receipt = one matching protected call only; changed input + retry require another stop.
- Unrequested protected delivery action = state exact target + remote + branch + effect → ask once.
- Ready-to-build approval ≠ unrequested protected delivery authorization; missing material delivery choice = one decision.
- Explicit terminal delivery outcome persists across recoverable build/CI failures, retries, and turn boundaries; one failed attempt never narrows the goal.
- Missing project gate manifest/family = invalid green snapshot → `he-build` + `deterministic-checks` `gate-migration`; Ship never wires it.
- Sync/content/CI change → `he-build` final loop; green evidence becomes stale.
- `assert-green` = working artifact at Ship entry; `assert-green --delivered-head` = post-commit HEAD/index/worktree exactness before push; either failure returns to `he-build`.
- Publish gate = `deterministic-checks` `publish` PASS on exact intended diff.
- Delivery SHA = remote product artifact identity; later local lifecycle-state bytes are not part of that artifact.
- Force push + bypassed hook/check + hidden path + fabricated remote result = forbidden.
- Rollback + observability + protected-boundary evidence = retained through delivery.
- Process learning = record + defer without blocking unless continued delivery risks a protected boundary.
- Stop = user override OR protected-boundary stop OR exact external authority blocker; deterministic product/tool failure → `he-build` + resume Ship.

## Complete

- Delivered artifact = exact green reviewed snapshot.
- Remote ref/PR/merge + required CI = verified.
- Repository delivery contract = satisfied.
- `he` local checkpoint = `lifecycle_status=shipped` + delivery SHA/URL/result in `next_action`; it does not rewrite delivered artifact identity or imply another commit.
