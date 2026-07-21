# Feature Stage

## Decide

| Area | Required decision |
|---|---|
| Problem | affected users + current workaround + evidence + frequency/severity + consequence of no change |
| Outcome | user outcome + business outcome + measurable success + guardrails + why now |
| Boundary | scope + non-goals + minimum useful version + deferred capability |
| Constraint | dependency + technical/product/legal/operational constraint |
| Policy/default | eligibility + inclusion/exclusion + permission/role + initial/default state + explicit opt-out/override behavior |
| Acceptance | observable positive + negative + permission + failure/recovery behavior |

- Proposed solution ≠ problem evidence.
- Vague quality (`simple`, `fast`, `intuitive`) → measurable threshold or unresolved question.

## Route

1. Compare accepted feature intent against root `PRODUCT.md` → record no-delta or apply Stage Route product-context update + explicit approval.
2. Separate requested solution → observed problem/current workaround.
3. Join research evidence → affected users + frequency/severity + why now.
4. Define user/business outcomes → measurable success + guardrails.
5. Bound minimum useful scope → non-goals + deferrals + constraints/dependencies.
6. Assign `R-*` IDs; convert outcomes → observable acceptance, including negative/permission/recovery behavior; every material policy/default → `D-*` with alternatives + selected behavior + authority/evidence.
7. Challenge solution bias, vague measures, hidden scope, and unsupported urgency.

## Complete

- Root `PRODUCT.md` exists + validates + reflects approved intended truth.
- Current behavior cited; desired behavior explicitly user-approved.
- Every acceptance statement has one stable `R-*` ID + observable behavior + scope owner.
- Assumptions, contradictions, dependencies, decisions, defaults, non-goals = explicit; `safe|eligible|approved|permission-aware` never substitutes for exact included/excluded behavior.
- Skip proposal only when `PRODUCT.md` is valid/current + no product behavior/outcome changes.
