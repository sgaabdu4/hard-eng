---
name: he-ship
description: Deliver one exact green Hard Eng snapshot through publish gates, authorized Git actions, and required CI.
---

# Hard Eng Ship

## Contract

- Input = `$he` route + approved PLAN + `lifecycle_status=green` + exact green snapshot.
- Output = verified repository-policy delivery + `shipped`, or return to `$he-build`.
- Owner = sync + snapshot continuity + publish gates + authorized commit/push/PR/CI/merge + delivery receipt.
- Code/test/doc fixes = `$he-build`; ship never patches a failing artifact.
- Load [workflow.md](references/workflow.md) before shipping or resume.

## Invariants

- Destructive/external/commit/push/PR/merge/publish action = exact target + remote + branch + scope approval.
- Generic workflow/build approval ≠ delivery approval.
- Existing exact authorization = continue; missing material delivery choice = one question.
- Sync/content/CI change → `$he-build` final loop; green evidence becomes stale.
- `assert-green` = working artifact at Ship entry; `assert-green --delivered-head` = post-commit HEAD/index/worktree exactness before push; either failure returns to `$he-build`.
- Publish gate = `$deterministic-checks` `publish` PASS on exact intended diff.
- Delivery SHA = remote product artifact identity; later local lifecycle-state bytes are not part of that artifact.
- Force push + bypassed hook/check + hidden path + fabricated remote result = forbidden.
- Rollback + observability + protected-boundary evidence = retained through delivery.
- Process learning = asynchronous/non-blocking unless continued delivery risks a protected boundary.

## Complete

- Delivered artifact = exact green reviewed snapshot.
- Remote ref/PR/merge + required CI = verified.
- Repository delivery contract = satisfied.
- `$he` local checkpoint = `lifecycle_status=shipped` + delivery SHA/URL/result in `next_action`; it does not rewrite delivered artifact identity or imply another commit.
