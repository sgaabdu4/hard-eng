# Contracts Stage

## Decide

| Area | Required decision |
|---|---|
| Boundary | authoritative routes/schemas/events/generated owners + callers/consumers |
| Access | authentication + authorization + permission + tenancy enforcement |
| Default | absent-row/missing-field behavior + eligibility/inclusion/exclusion + override/opt-out precedence |
| Operation | purpose + method/input/output + validation + status/error codes + pagination/filter/sort |
| Resilience | idempotency + timeout/retry/rate limit + duplicate/concurrent/partial/async behavior |
| Data | entity/ID/fields/defaults/relations + ownership/SSOT + lifecycle/retention/deletion/audit |
| Change | migration/backfill/rollback + compatibility/versioning + event/webhook/notification behavior |
| Proof | mock fixtures/examples; OpenAPI only when generated/reviewed contract complexity earns it |

## Route

1. Trace approved flow actions → existing authoritative interfaces + callers/consumers/generated owners.
2. Mark reuse/change/new boundaries; reject duplicate or UI-only permission ownership.
3. Define access + defaults + operation semantics, then error/retry/concurrency/partial behavior; new restrictive/permissive default requires a cited `D-*` decision.
4. Define data SSOT + lifecycle; derive migration/backfill/compatibility/rollback when shape changes.
5. Build fixtures/examples from accepted semantics; generate OpenAPI only when independently consumed/reviewed.
6. Assign `C-*` IDs; reconcile UI states ↔ data/errors, permissions ↔ backend enforcement, events ↔ consumers.
7. For each external/async transition, define durable pre/post state + acceptance ambiguity + retry/timeout + duplicate/concurrent + recovery-exhaustion behavior.
8. Concrete cross-boundary failure/guarantee → bind authoritative owner + finite domain/cutoff + executable query/algorithm + fence/cleanup + quantitative bound/retention in `## Guarantee Model`.

## Complete

- UI action ↔ backend behavior; UI state ↔ required data; backend error ↔ recovery behavior.
- Permissions = backend-enforced; fixtures = accepted contracts; generated source owner identified.
- Every contract decision maps by ID to flow + failure model + test + slice.
- Skip proposal only when no interface/data/auth/event/integration change exists.
