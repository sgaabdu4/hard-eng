---
name: he-build
description: Execute an approved PLAN through Implement ⇄ Verify until its exact local snapshot is green.
---

# Hard Eng Build

## Contract

- Input = `$he`-selected fresh PLAN + `route_target=$he-build` + repository `write` PASS.
- Output = checkpointed `building` progress + durable pause or exact-snapshot `green`.
- Owner = build sequence + findings convergence + readiness + lifecycle transition.
- Publish/rebase/commit/push/PR/CI = `$he-ship`; forbidden here.
- Load [workflow.md](references/workflow.md) before mutation or resume.

## Ownership

| Evidence | Owner |
|---|---|
| Behavior/TDD/assertion strength | `$test-quality` |
| Commands/analyzers/scanners/hooks | `$deterministic-checks` |
| Standards + Spec review | `$code-review` |
| Security trust paths | `$security-review` |
| UI tokens/components/a11y | `$atomic-ui` + stack skill |
| Real browser/device + artifacts | `$e2e` |
| Repeated root failure | `$repeated-failure-learning` |

## Invariants

- Unit = one approved vertical slice + observable behavior.
- Loop = TDD RED → GREEN → REFACTOR ⇄ focused proof ⇄ accepted finding fix.
- Current task = implementation/fix owner; final auditor = ephemeral read-only `codex exec`.
- Auditor input = bounded complete packet; child = empty read-only Git workspace + zero tools; source/home = inaccessible.
- Non-PLAN content/staging mutation → new artifact/snapshot + prior build evidence stale; PLAN integrity = checkpoint token.
- Finding = exact snapshot + axis + severity + evidence + root owner + disposition + next proof.
- Authorized fixable finding → fix root + connected blast radius → affected proof → review again.
- User decision/external authority/repeated unresolved root → PLAN item + exact pause; guessing/spinning = forbidden.
- Readiness score = visibility only; failed hard axis cannot be compensated.
- PLAN `build_axes` = canonical statuses; validator derives readiness + blocks incomplete green.
- Checkpoint after slice/finding/evidence/status change + before question/handoff/compaction/turn end.

## Complete

- Every planned slice = complete + demonstrated.
- Every applicable axis = PASS; N/A = evidence-backed.
- Build readiness = `100`; blocker/issue/unknown count = `0`.
- E2E/runtime proof = complete; UI → required screenshots + primary-flow video + durable-state proof.
- Final independent audit = valid + exact current snapshot + zero unresolved required finding.
- PLAN build evidence = current; transition to `green` through `$he` state owner; stop.
