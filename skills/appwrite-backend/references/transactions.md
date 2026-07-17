# TablesDB Transactions

## Contract

- Transaction = staged TablesDB row operations + explicit commit/rollback.
- Atomic scope = supported row/bulk/operator operations across tables/databases.
- Excluded = schema + Auth + Storage + Functions + external providers.
- Read-own-writes = every dependent read/write carries the same `transactionId`.
- Client context = one authenticated client/transaction owner; independent helper client = stale-read risk.

## Sequence

1. Create transaction → retain exact `$id`.
2. Stage related operations with `transactionId`.
3. Read dependent rows with the same `transactionId`.
4. Validate invariant against staged state.
5. Commit explicitly; failure/decision change → roll back explicitly.
6. Exact post-commit read-back → side-effect reconciliation.

```typescript
const tx = await tablesDB.createTransaction();

await tablesDB.updateRow({
  databaseId: 'main',
  tableId: 'accounts',
  rowId: sourceId,
  data: {credits: Operator.decrement(amount)},
  transactionId: tx.$id,
});

await tablesDB.updateRow({
  databaseId: 'ledger',
  tableId: 'accounts',
  rowId: targetId,
  data: {credits: Operator.increment(amount)},
  transactionId: tx.$id,
});

const staged = await tablesDB.getRow({
  databaseId: 'ledger',
  tableId: 'accounts',
  rowId: targetId,
  transactionId: tx.$id,
});

await tablesDB.updateTransaction({transactionId: tx.$id, commit: true});
```

SDK signature = installed target version. Generated SDK/source wins over copied syntax.

## Conflicts + Retries

- Commit conflict = affected row changed outside transaction.
- Retry = re-read current source → rebuild every staged decision → new transaction.
- Replaying stale operations or reusing an expired transaction = forbidden.
- Keep transaction short; no provider/network work while holding staged decisions.
- Max operations = plan/server dependent; inspect target limits before chunking.
- Preflight = remove no-op/scoped work → count every staged operation → compare with bound target cap + headroom before transaction creation.
- Over budget = split only at invariant-safe boundaries OR redesign ownership; partial transaction construction = forbidden.

## Cross-Service Side Effects

| Side effect | Owner |
|---|---|
| TablesDB rows | transaction |
| Storage file ACL/content | compensation + exact file read-back |
| Auth user/team | compensation + reconciliation |
| Function/provider/email | outbox/idempotency key + convergence worker |
| Schema | [production-migrations.md](production-migrations.md) expand/contract |

- Database commit + Storage mutation cannot be one Appwrite transaction.
- Safe order = stage rows → perform required pre-commit checks → commit → apply post-commit side effects → reconcile/compensate failures.
- Security revocation spanning rows/files = deny stale access on every surface; partial success must remain visible as failure until converged.

## Proof

- Success test = all staged writes visible after commit.
- Failure test = injected late row failure leaves no committed row mutation.
- Staged-read test = helper observes prior staged change through same transaction.
- Conflict test = concurrent change rejects commit + fresh rebuild succeeds.
- Budget test = exact-cap fixture passes; cap+1 fails before transaction creation; removed no-op work is not counted.
- Cross-service test = Storage failure restores/finishes ACL state deterministically.

## Sources

- <https://appwrite.io/docs/products/databases/transactions>
- <https://appwrite.io/docs/references/cloud/server-nodejs/tablesDB>
