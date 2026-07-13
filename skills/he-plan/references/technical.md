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

- Module/API/ownership/seam evidence = `$codebase-design`.
- Trust/auth/data/security evidence = `$security-review`.

## Route

1. Map approved flows/contracts → current owners, direct callers, cross-package/system effects, and generated sources.
2. Use `$codebase-design` → produce canonical owners + public contracts + deletable concepts + blast radius.
3. Material interface choice → use `$codebase-design` alternatives → obtain user selection through `$question-me`.
4. Trace data/state/runtime + failure/recovery across every selected owner.
5. Security-sensitive path → use `$security-review`; apply remaining quality/change inventory → constraint + mechanism + owner + proof.
6. Challenge unresolved ownership, hidden modes/fallbacks, races, trust crossings, migration/rollback gaps, and blast-radius omissions.
7. Reconcile selected design against flow/contract/UX owners; unresolved conflict returns to affected stage.

## Complete

- Proposed approach cites current owners/callers and covers declared blast radius.
- Each flow/contract has one implementation owner + failure path.
- Cross-cutting constraints + meaningful alternatives = resolved or explicitly blocked.
- Skip proposal only for a proven no-code/no-architecture change.
