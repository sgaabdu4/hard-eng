# Testing Stage

## Decide

| Area | Required decision |
|---|---|
| Environments | local/CI/staging/runtime constraints + test data/fixture owner |
| Behavior | acceptance + unit + integration + contract + E2E + manual exploration as applicable |
| Boundaries | permission/tenant + security + accessibility + browser/device |
| Failure | negative/recovery + resilience + performance + migration + rollback |
| Gates | project analyzers/linters/scanners/tests + hook/CI owner + exact commands/evidence |

Traceability = `requirement → flow → UI/system state → contract/owner → proof → telemetry`.

## Route

1. Expand approved requirements/flows/contracts/technical risks → traceability rows.
2. Choose the lowest public boundary that proves each behavior; add broader layer only for uncovered integration risk.
3. Add negative/permission/tenant/recovery + applicable accessibility/security/performance/migration/rollback cases.
4. Define environment + fixture/mock/real-data boundary + deterministic pass criterion per row.
5. Inspect existing scripts/hooks/CI → exact project gates; add/change gate only for a recurring enforceable violation.
6. Challenge tests that cannot fail, assert internals, duplicate proof, or leave required runtime/device coverage unavailable.

## Complete

- Every material requirement has positive + relevant negative/permission/recovery proof.
- Each test names public behavior, layer, environment, data, and pass criterion; generic `test feature` = invalid.
- Existing baseline + new/changed deterministic gate = explicit.
- Skip proposal only when evidence proves no behavior can regress.
