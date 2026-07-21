---
name: he-plan
description: Advance PLAN stages validated by $he; pause only for material decisions.
---

# Hard Eng Plan

## Contract

- Input = `$he`-selected fresh `PLAN.md` + `plan_stage`.
- Output = automatic PASS chain to next route, or exact blocker/issue/unknown; production code/config mutation = forbidden.
- Owner = current accepted `PLAN.md`; split rules → final [artifacts.md](references/artifacts.md).
- Repository context gate = `$he`; invalid context blocks stage advance.

## Stage Route

Order = `repository → research → feature → flows → ux → contracts → technical → testing → rollout → slices → consistency → approval`.

| `plan_stage` | Load | Stage result |
|---|---|---|
| `repository` | [repository.md](references/repository.md) + `$research` + `$deterministic-checks` | repository/revision + root context pair approved |
| `research` | [research.md](references/research.md) + `$research` | code + product/design truth/drift proven or blocked |
| `feature` | [feature.md](references/feature.md) + [product.md](references/product.md) | product delta/no-delta + feature outcome/scope accepted |
| `flows` | [flows.md](references/flows.md) | actors + state/failure paths accepted |
| `ux` | [ui.md](references/ui.md) + `$atomic-ui` | design delta/no-delta + UX skip/prototype accepted |
| `contracts` | [contracts.md](references/contracts.md) | skip approved, or interfaces/data accepted |
| `technical` | [technical.md](references/technical.md) | owners + approach + cross-cutting design + audit `risk_tier` accepted |
| `testing` | [testing.md](references/testing.md) | requirement-to-proof coverage accepted |
| `rollout` | [operations.md](references/operations.md) | release/observe/recover plan accepted |
| `slices` | [slices.md](references/slices.md) | vertical delivery order accepted |
| `consistency` | [consistency.md](references/consistency.md) + [admission.md](references/admission.md) | trace gaps = zero + risk-tier plan challenge clean + executable admission PASS |
| `approval` | [artifacts.md](references/artifacts.md) | context + canonical plan explicitly approved |

- Load current row only; specialists = evidence owners, never stage/lifecycle owners.
- Repository context invalid → also load [product.md](references/product.md) + `$atomic-ui`; valid → do not load them.
- Prior stage not approved/skipped → stop; report first missing stage; never jump.
- Repository/research uncertainty → `$research`; desired-state uncertainty → `$question-me`.
- PLAN `## Audit policy` = exactly one `risk_tier = standard|critical`; payment/auth/security/privacy/destructive-data/uncertainty → `critical`; `standard` requires evidence that none applies.

## Gate

| Result | Action |
|---|---|
| User decision/review needed | Invoke `$question-me` Planning Stage; consume its authoritative review + verbatim response. |
| Changed material decision | Show delta → confirm changed intent → reopen earliest affected stage → auto-revalidate unchanged downstream proof. |
| Finding already contradicted concrete approved trace/failure row | Return implementation defect to current owner/build loop. |
| Finding adds/changes state/contract/owner/boundary/recovery/proof | Plan defect → reopen earliest affected stage even when product outcome is unchanged. |
| Evidence + accepted intent resolve stage | Record PASS → checkpoint → immediately execute current next stage. |
| Unambiguous approval + no material gap | Record approval → advance exactly one stage → immediately execute current next stage. |
| Skip proven + no material decision | Record irrelevance evidence + risk + mitigation → skip + advance; `consistency` + `approval` cannot skip. |
| Neither approved nor skipped | Persist exact blocker/issue/unknown + next action → remain at current stage. |
| Before question/handoff/turn end | Invoke `$he` checkpoint contract. |
| Proven learning trigger at stage boundary | Invoke `$he-learn` candidate capture; keep `plan_stage` unchanged. |
| Final approval | Require [admission.md](references/admission.md) PASS + apply [artifacts.md](references/artifacts.md) → ask whether `PLAN.md` fully represents intended implementation → explicit yes transitions to `build-ready`. |

- Stage PASS = commentary + checkpoint + same-turn continuation; final answer/`continue?` between stages = forbidden.
- Stage name/transition ≠ approval boundary; generic `continue`/`yes` request = forbidden.
- Reopen revalidates unchanged downstream stages automatically; generic downstream reapproval = forbidden.
- Pause for approval only when unresolved material choice or explicit external boundary requires it; final full-PLAN approval remains mandatory.
- `build-ready` + implementation requested → route `$he-build` same turn; explicit plan-only scope → deliver plan + stop.
- Pause only = `CONCERNS|FAIL` + required user decision + explicit scope end + external boundary.
