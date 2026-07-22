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

## Ownership

- Behavior/seam/scenario/assertion/mutation design = `$test-quality`.
- Real browser/device UI proof = `$e2e`; planning defines scenario + environment + evidence mode only.
- Exact commands/analyzers/scanners/hooks/CI = `$deterministic-checks`.

## Route

1. Assign `T-*` IDs; expand approved requirements/flows/contracts/technical risks + every `FM-*` row → traceability rows.
2. Use `$test-quality` → obtain named behavior/risk proof design per row; record its layer + pass criterion.
3. Real browser/device proof needed → use `$e2e` → record scenario + environment + evidence mode.
4. Record environment + data/fixture owner + availability per row; unavailable required proof → blocker.
5. Use `$deterministic-checks` → record existing baseline + exact project gates; new wiring only for a recurring enforceable violation.
6. Verify traceability rows cover every requirement/risk with proof, `N/A` + reason, or explicit unknown + next proof.

## Complete

- Every material requirement/risk/transition/failure timing → delegated proof design + layer + environment/data + pass criterion + gate/telemetry, or explicit `N/A`/unknown.
- High-risk state machine → failure injection/model/property proof for transition totality + idempotency + recovery ownership; happy-path integration proof alone = incomplete.
- Typed guarantee proof distinguishes active work/external effects from retained terminal evidence and tests finite completion, stale-fence rejection, cleanup, and exact timing boundaries named by its `G-*` row.
- Existing baseline + exact new/changed deterministic gate = explicit.
- Skip proposal only when `$test-quality` evidence proves no material behavior or delivery risk requires testing.
