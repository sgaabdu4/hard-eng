---
name: test-quality
description: Design or review behavior tests, QA coverage, TDD, or mutation strength.
---

# Test Quality

## Contract

- Behavior owner = product/spec/public contract + verified implementation boundary.
- Proof target = observable behavior at narrowest meaningful public seam; implementation detail ≠ behavior.
- Refactor without behavior change → test remains valid.
- Strength proof → intended behavior break makes test fail; coverage/pass alone ≠ effective test.

## Route

| Work | Load | Completion |
|---|---|---|
| Test/QA design, review, regression, mutation | [workflow.md](references/workflow.md) | Required scenarios + sensitivity + strength proven |
| Explicit TDD/red-green-refactor | [tdd.md](references/tdd.md) | Every behavior increment completes RED → GREEN → REFACTOR |

## Ownership

- This skill owns: behavior model + seam + scenarios/edges + doubles + assertions + red evidence + mutation interpretation.
- `$deterministic-checks` owns: exact commands + analyzers/linters/scanners + hooks + CI wiring/results.
- Existing test framework/project conventions = reuse; new framework/dependency requires explicit need + approval.

## Test Case

`behavior ID → precondition/data → user/system action → observable result → negative/edge boundary → proof layer`

## Completion

- Every material behavior/risk → ≥1 proof; every test → named behavior/risk.
- Positive + relevant boundary/negative/permission/recovery/concurrency cases = covered or `N/A` + reason.
- New/changed test has red/sensitivity evidence for intended reason, then passing evidence.
- Mutation used where risk/cost justifies it; survivor disposition = test gap fixed / equivalent / invalid / deferred with consequence.
- Flake, implementation coupling, duplicate proof, permissive assertion, or internal mock = `CONCERNS` until resolved.
