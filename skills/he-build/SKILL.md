---
name: he-build
description: Execute an approved PLAN one demonstrable vertical slice at a time until the actual implementation is green.
---

# Hard Eng Build

## Contract

- Input = `$he` route + approved PLAN Feature Brief + Ready-to-build approval + `lifecycle_status=build-ready|building` + repository `write` PASS.
- Output = demonstrated slices + one successful full pre-ship gate + exact local `green` snapshot.
- Owner = Implement ⇄ Verify loop + actual diff review + affected behavior proof + build findings.
- Publish/rebase/commit/push/PR/CI = `$he-ship`; forbidden here.
- Load [workflow.md](references/workflow.md) before mutation or resume.

## Ownership

| Evidence | Owner |
|---|---|
| Behavior/RED/GREEN/assertion quality | `$test-quality` |
| Commands/analyzers/scanners/hooks | `$deterministic-checks` |
| Actual implementation diff | `$code-review` |
| Auth/security/privacy/data boundaries | `$security-review` |
| Data-loss/irreversible/schema/recovery boundary | `$code-review` + applicable domain/test/runtime owner |
| UI owner/tokens/components/a11y | `$atomic-ui` + stack skill |
| Real browser/device behavior | `$e2e` |
| Repeated implementation root | `$repeated-failure-learning` |
| Proven process gap | `$he-learn` |

## Invariants

- Work unit = one active independently demonstrable vertical slice.
- Loop = reproduce/RED where applicable → canonical-owner change + connected callers/schema/routes → targeted GREEN → SSOT/DRY/YAGNI refactor → actual-diff review → relevant E2E/security proof.
- One active slice only; slice completion requires observable behavior, not path/task completion.
- Build-ready entry = preserve completed slices + select first remaining slice; progress reset = forbidden.
- Standard work = one actual-diff review + scoped re-review only for accepted findings.
- Critical/risky slice = standard review + targeted independent review by every applicable protected-boundary owner; whole-feature ceremony is forbidden merely because one slice is risky.
- Implementation finding = verify → root fix in current loop → affected proof → scoped re-review.
- Planning reopens only when evidence changes accepted outcome OR adds/changes a material security/privacy/data-loss/irreversible contract.
- Caller/path/schema/test discovery inside accepted outcome = implementation work; planning reapproval is forbidden.
- Candidate patches + path manifests + patch/hash admission + repeated final LLM audits = forbidden.
- Learning = asynchronous non-blocking `$he-learn`; current build pauses only when continued work risks a protected boundary.
- Security/trust/privacy/accessibility/schema/data-loss protections + rollback/observability = preserved.
- Checkpoint after slice/status/material finding change + before pause/handoff/turn end.

## Complete

- Every accepted slice = implemented + demonstrated.
- Actual diff = reviewed; accepted findings = closed by affected proof + scoped re-review.
- Applicable risky boundary + E2E evidence = PASS.
- Docs/context = accepted current behavior.
- One successful full pre-ship gate = current exact local snapshot.
- Blocker/unknown count = zero.
- `$he` checkpoint = `lifecycle_status=green`; authorized delivery → `$he-ship`.
