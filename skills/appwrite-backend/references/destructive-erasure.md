# Destructive Subject-Data Erasure

## Contract

- Scope = every locally owned row, Auth identity, Storage object, message/file derivative, and indirect subject link + explicitly retained audit/provider evidence.
- Completion = durable final audit + exact residual-data queries prove the declared local scope is gone.
- Preview + execution = one canonical ownership registry + one plan builder; preview counts deletable history as scope, never as a blocker.
- Appwrite transaction scope = TablesDB only. Auth + Storage + Functions + providers require explicit idempotency + reconciliation through [transactions](transactions.md).
- Provider-owned retained evidence = named boundary + retention owner; never claim it was locally erased.

## Ownership Closure

1. Inventory every persistence owner + direct/indirect subject identifier.
2. Keep one machine-readable registry mapping each subject-linked table/field/resource to `delete`, `delete-or-detach`, `covered-by-owner`, `retain-final-audit`, or `provider-owned`.
3. Gate schema changes: new/renamed subject-linked table/field without one exact disposition = failure; stale registry entry + unknown disposition + unsupported relationship bulk path = failure.
4. Treat field-name matching as candidate discovery only. Closure requires schema-owner review or metadata that forces every new persistence owner to declare its subject-data disposition.
5. Resolve indirect links before mutation: owner rows → booking/session/conversation/change IDs → dependent rows/files.
6. Preserve only the minimum final audit; exclude contact, payment, request/response body, credentials, and deleted subject content.

## Workflow

1. Authorize the actor + exact subject + irreversible confirmation + reason.
2. Build a fully paginated plan from the registry; deduplicate exact row/file/Auth IDs.
3. Preview the same plan + validate bulk/query/transaction limits + reject empty delete queries.
4. Create a deterministic pending audit before irreversible work; retry reuses its ID.
5. Choose the declared cross-service order → apply only the side effects required before the database lane. After deterministic target preflight, retry-time Auth/Storage `404` = idempotent completion; an unresolved first-attempt `404` = target mismatch, not success. Retry must use a service/admin identity, never the deleted subject session.
6. Start a fresh TablesDB transaction → rebuild the plan → stage shared-row detach/update + exact-ID bulk deletes.
7. For every `deleteRows` call, compare the returned Rows List ID set with the planned chunk. Missing or unexpected ID = invariant failure → no commit.
8. Mark the audit completed with exact per-owner counts inside the same transaction → commit once.
9. Apply declared post-commit side effects + reconcile every cross-service postcondition.
10. Commit response lost/throws → read the deterministic completed audit + exact postcondition. Proven completed = success; otherwise failed/unknown + retryable reconciliation.
11. Post-commit query every registry rule to fixed point; local residual count must be `0` except the declared final audit.

Cross-service order has no universal default. Choose from the protected invariant:

- Prevent login first → revoke/delete Auth before local data commit; keep retries service-authenticated.
- Preserve local retry evidence first → pending audit + complete plan before Auth/Storage deletion.
- Provider data legally retained → do not call provider deletion; delete only local payment-linked rows + state the boundary.
- Irreversible side effect cannot be compensated → partial success remains visible until idempotent retry converges.

## Failure Transport

- Function response = stable code + fixed safe message + allowlisted diagnostic fields.
- Useful allowlist = stage + primary/recovery error type + Appwrite code/type + transaction/execution ID + table ID + expected/actual count + invariant reason.
- Raw exception message + stack + function `errors` + response body stay server-side; never forward them to browser telemetry.
- Sync `createExecution` → consume returned `status` + `responseStatusCode` + `responseBody`; async execution → bounded reconciliation. See [functions-advanced](functions-advanced.md).
- Rollback/cleanup failure stays secondary; preserve the primary cause + both stack traces. See [transactions](transactions.md).

## Proof

- Coverage gate = add a subject-linked table/field fixture → fail until disposition + execution owner exist.
- Plan parity = preview IDs/counts equal execution-plan IDs/counts for unchanged source state.
- Exact staging = returned bulk IDs reordered → pass; missing/unexpected ID → fail before commit.
- Atomic database failure = injected late staging/audit failure leaves every TablesDB row unchanged.
- Cross-service retry = Auth/Storage succeeds + database commit fails → second run converges without subject session or duplicate audit.
- Ambiguous commit = thrown/lost response + completed audit/postcondition → success; absent receipt + residual rows → failure.
- Idempotency = repeated completed request returns the stored final counts.
- Privacy = client/browser telemetry contains only allowlisted diagnostics.

## Sources

- Transactions + read-own-writes: <https://appwrite.io/docs/products/databases/transactions>
- Bulk operations + transaction staging: <https://appwrite.io/docs/products/databases/bulk-operations>
- Dart `deleteRows` response = Rows List: <https://appwrite.io/docs/references/cloud/server-dart/tablesDB#delete-rows>
