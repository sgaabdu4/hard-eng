# Technical Stage

## Decide

| Area | Required decision |
|---|---|
| Blast radius | apps/services/packages/routes/components + callers + repositories/systems + generated owners |
| Ownership | existing code reused + canonical new/changed owners + data/state flow |
| Runtime | dependency/integration + job/queue/cache + concurrency + failure/recovery |
| Quality | security + privacy + accessibility + performance + reliability + observability + cost |
| Change | migration + compatibility + deployment + rollback + irreversible boundary |
| Choice | meaningful alternatives + recommendation + trade-offs + user decision + revisit trigger |

- Architecture = fewest complete concepts; no pass-through wrapper, parallel owner, or speculative layer.
- Security includes trust boundaries, tenant isolation, validation, exposure, secrets, abuse, audit, destructive action as applicable.

## Route

1. Map approved flows/contracts → current owners, direct callers, cross-package/system effects, and generated sources.
2. Design the fewest-complete-concept path: reuse owners → modify owners → add owner only from proven gap.
3. For each material choice, produce evidence-backed alternatives + trade-offs + recommendation + revisit trigger; obtain user selection through `$question-me`.
4. Trace data/state/runtime + failure/recovery across every selected owner.
5. Apply quality/change inventory → explicit constraint, mechanism, owner, and proof.
6. Adversarially challenge wrong ownership, wrappers, hidden modes/fallbacks, races, trust crossings, migration/rollback gaps, and blast-radius omissions.
7. Reconcile selected design against flow/contract/UX owners; unresolved conflict returns to affected stage.

## Complete

- Proposed approach cites current owners/callers and covers declared blast radius.
- Each flow/contract has one implementation owner + failure path.
- Cross-cutting constraints + meaningful alternatives = resolved or explicitly blocked.
- Skip proposal only for a proven no-code/no-architecture change.
