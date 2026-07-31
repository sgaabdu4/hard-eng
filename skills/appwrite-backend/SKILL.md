---
name: appwrite-backend
description: Appwrite backend development and operations. Use for Appwrite SDK work; any Appwrite CLI command or failure must route through the CLI safety branch.
license: MIT
metadata:
  author: sgaabdu4
  version: "2.0.12"
  tags: appwrite, backend, baas, dart, python, typescript
---

# Appwrite Development

## Route

Load the owner before acting. Unlisted detail = read the owner, never infer.

| Trigger | Owner |
|---|---|
| Any Appwrite CLI/wrapper command, deployment, schema sync, function/site variable operation, or CLI failure — before installing, binding, probing, diagnosing, or mutating | [appwrite-cli](references/appwrite-cli.md) |
| Production schema/data/ACL/function cutover | [production-migrations](references/production-migrations.md) + CLI owner when CLI participates |
| TablesDB transaction or cross-service consistency | [transactions](references/transactions.md) + [permissions](references/permissions.md) |
| Mass row create/update/upsert/delete, transaction-limit pressure, per-row write loop | [bulk-operations](references/bulk-operations.md) + [transactions](references/transactions.md) when atomic scope spans requests/tables |
| Filter by more IDs than the deployed `Query.equal()` value cap | [chunked-queries](references/chunked-queries.md) |
| Table/column/index design, encryption at rest, auto-increment, timestamp override, CSV import/export | [schema-management](references/schema-management.md) |
| Query shape, `select`, spatial, time helpers, missing-index suspicion | [query-optimization](references/query-optimization.md) |
| Counter, array, string, or date field mutated concurrently | [atomic-operators](references/atomic-operators.md) |
| Relationship modeling or traversal | [relationships](references/relationships.md) |
| List, feed, infinite scroll, or large-offset paging | [pagination-performance](references/pagination-performance.md) |
| Slow path, caching, delta sync, bootstrap ordering | [performance](references/performance.md) |
| Bandwidth, execution, or storage cost | [cost-optimization](references/cost-optimization.md) |
| Sessions, MFA, SSR auth, JWT, user labels, security settings | [authentication](references/authentication.md) |
| OAuth, magic link, email OTP, phone, anonymous, custom token | [auth-methods](references/auth-methods.md) |
| ACL design, lockout, public-leak suspicion | [permissions](references/permissions.md) |
| Team, membership, or multi-tenancy | [teams](references/teams.md) |
| Upload, download, preview, transform, bucket config | [storage-files](references/storage-files.md) |
| Function authoring, handler, runtime, cold start, env vars | [functions](references/functions.md) |
| Function events, schedules, idempotency, binary payloads, CI/CD | [functions-advanced](references/functions-advanced.md) |
| Realtime subscription, channel, presence, event filtering | [realtime](references/realtime.md) |
| Push, email, or SMS delivery | [messaging](references/messaging.md) |
| Outbound event delivery to an external system | [webhooks](references/webhooks.md) |
| Avatar, initials, QR, flag, favicon | [avatars](references/avatars.md) |
| `429`, retry, typed error, timeout | [error-handling](references/error-handling.md) |
| Platform ceiling or limit error | [limits](references/limits.md) |
| Country, currency, language, or geo lookup | [locale](references/locale.md) |
| GraphQL endpoint | [graphql](references/graphql.md) |
| Self-hosted install, config, security, scaling, SDK version pins | [self-hosting](references/self-hosting.md) |
| Self-hosted backup, restore, upgrade, data-loss incident | [self-hosting-ops](references/self-hosting-ops.md) |
| Health check, queue depth, uptime monitoring | [health](references/health.md) |

## Invariants

1. **Official SDK only** — raw Appwrite HTTP (`fetch`, `requests`, `dio`, `package:http`, `curl`) is a violation unless the SDK lacks the endpoint or an isolated, tested `Client.call` works around SDK model parsing.
2. **Pin SDKs by target and call shape** — Cloud: latest stable official SDK. Self-hosted `1.9.x`: exact release-matched pins in [self-hosting](references/self-hosting.md). “Compatible with `1.9.x`” does not mean release-matched. Before changing a pin, audit every intervening breaking change and prove the repository's real SDK calls against the candidate; version resolution alone is insufficient. Repository-pinned binary/wrapper version always outranks a skill pin.
3. **TablesDB, not Collections** — Collections/Documents API deprecated 1.8.0.
4. **Allocate Appwrite IDs once with `ID.unique()`** — retryable create: call `ID.unique()` before the first attempt → persist the returned ID in the durable draft/intent → reuse that exact ID for every retry/reconciliation. A fresh `ID.unique()` on retry creates a second resource. Business/natural identity remains in indexed columns; never derive resource IDs from names, timestamps, slugs, hashes, or custom generators.
5. **Explicit ACL** — server SDK/Console create = empty resource ACL; client SDK create = creator read/update/delete. Pass explicit `Permission`/`Role` whenever ACL correctness matters.
6. **Bind limits to the deployed target** — page size, bulk rows/request, transaction operations, and `Query.equal()` value cap come from the deployed server source/config, never from memory.
7. **Async-start long-running Functions** — client `createExecution` for delete/sync/import/export/migrate/generate uses async execution, then reconciles source-of-truth state with bounded polling/realtime/fetch. Report destructive failure only after reconciliation proves the entity still exists. A synchronous `createExecution` already returns the terminal execution → read `responseStatusCode` + `responseBody` off that response; polling `getExecution` from the creating session returns `404` and inverts a success into a failure. Unavoidable status poll → `404` = terminal-unknown, never an error branch. Use [functions-advanced](references/functions-advanced.md).
8. **Guard schema pushes** — `appwrite push tables` reconciles remote TablesDB against the complete local manifest; omission means deletion. Production push requires [appwrite-cli](references/appwrite-cli.md) inventory + manifest guard PASS. `push all`, `--all`, and `--force` never substitute for that gate.
9. **Stage production migrations** — additive expand → type-aware resumable backfill → compatible deployment → contract/read-back → consumer activation. Partial data/schema never activates downstream code. Use [production-migrations](references/production-migrations.md).
10. **Preserve write intent before optimizing** — update-only work never routes through `upsertRow`/`upsertRows`; a pre-read, existence check, or full payload does not remove create-on-missing semantics. Same patch across rows → `updateRows`; heterogeneous per-row updates → `createOperations` with `action: update` inside the verified transaction budget, or redesign. Transaction pressure never authorizes upsert. Use [bulk-operations](references/bulk-operations.md).
11. **Preserve failure causality** — cleanup, compensation, or rollback failure never replaces the primary exception. Retain both errors + stack traces + execution/transaction IDs, report the operation failed, then reconcile the exact postcondition. Use [transactions](references/transactions.md).

## SDK Routing

| Runtime | Package |
|---|---|
| Web TypeScript/JavaScript/React | `appwrite` |
| Node.js/Deno/TypeScript SSR/Functions | `node-appwrite` |
| Flutter client | `appwrite` |
| Dart server/Functions | `dart_appwrite` |
| Python server/Functions | `appwrite` |

- Call style: TypeScript object parameters, Python keyword arguments, Dart named parameters. Positional only when matching existing code or on explicit request.
- Client SDKs use account sessions and user-scoped APIs. Server SDKs use API keys. SSR uses two clients: a reusable admin client for session creation, and a per-request session client via `setSession(...)` — never shared.
- Cloud project endpoint = `https://<REGION>.cloud.appwrite.io/v1`. The CLI account login endpoint stays `https://cloud.appwrite.io/v1`; do not rewrite it to a region.
- Initialize clients outside warm Function handlers where the runtime allows.

```typescript
import { Client, TablesDB } from 'node-appwrite';
const client = new Client()
    .setEndpoint('https://<REGION>.cloud.appwrite.io/v1')
    .setProject('<PROJECT_ID>')
    .setKey('<API_KEY>');
const tablesDB = new TablesDB(client);
```

```python
from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
client = (Client()
    .set_endpoint('https://<REGION>.cloud.appwrite.io/v1')
    .set_project('<PROJECT_ID>')
    .set_key('<API_KEY>'))
tables_db = TablesDB(client)
```

```dart
import 'package:dart_appwrite/dart_appwrite.dart';
final client = Client()
    .setEndpoint('https://<REGION>.cloud.appwrite.io/v1')
    .setProject('<PROJECT_ID>')
    .setKey('<API_KEY>');
final tablesDB = TablesDB(client);
```

## Terminology (1.8.0+)

Collections = Tables · Documents = Rows · Attributes = Columns · Databases = TablesDB

## Core Shapes

Row ops: `createRow` · `getRow` · `listRows` · `updateRow` · `upsertRow` · `deleteRow`
Bulk (server SDK only, atomic per request, rejects relationship columns): `createRows` · `updateRows` · `upsertRows` · `deleteRows`

```dart
await tablesDB.createRow(databaseId: 'db', tableId: 'users', rowId: ID.unique(),
    data: {'name': 'Alice'});

final rows = await tablesDB.listRows(databaseId: 'db', tableId: 'users',
    queries: [Query.equal('status', 'active'), Query.select(['name', 'email'])]);
```

**Query** (all prefixed `Query.`; per-SDK naming + semantics in [query-optimization](references/query-optimization.md)):
`equal` · `notEqual` · `lessThan` · `lessThanEqual` · `greaterThan` · `greaterThanEqual` · `between` · `notBetween` · `startsWith` · `endsWith` · `contains` · `search` (+ `not` variants) · `isNull` · `isNotNull` · `and` · `or` · `select` · `limit` · `offset` · `cursorAfter` · `cursorBefore` · `orderAsc` · `orderDesc` · `orderRandom` · `createdAfter` · `createdBefore` · `updatedAfter` · `updatedBefore` · `distanceEqual` · `distanceLessThan` · `distanceGreaterThan` · `intersects` · `overlaps` · `touches` · `crosses`

**Operator** (atomic field mutation; semantics in [atomic-operators](references/atomic-operators.md)):
`increment` · `decrement` · `multiply` · `divide` · `arrayAppend` · `arrayPrepend` · `arrayRemove` · `arrayUnique` · `arrayIntersect` · `arrayDiff` · `toggle` · `stringConcat` · `stringReplace` · `dateAddDays` · `dateSetNow`

**Column types** (`string` deprecated; full table + storage/index tradeoffs in [schema-management](references/schema-management.md)):
`varchar` · `text` · `mediumtext` · `longtext` · `integer` · `bigint` · `float` · `boolean` · `datetime` · `email` · `url` · `ip` · `enum` · `relationship` · `point` · `line` · `polygon`

**Realtime channels** (type-safe `Channel` helpers preferred over raw strings):
`account` · `tablesdb.<DB>.tables.<TABLE>.rows[.<ROW>]` · `buckets.<BUCKET>.files[.<FILE>]` · `teams[.<TEAM>]` · `memberships[.<MEMBERSHIP>]` · `functions.<FUNCTION>.executions` · `presences[.<PRESENCE>]`

## Anti-Patterns

| Wrong | Right | Why |
|---|---|---|
| Raw Appwrite HTTP (`fetch`, `requests`, `dio`, `package:http`, `curl`) | Official SDK package | Version drift, auth mistakes, lost typed APIs |
| `databases.listDocuments()` | `tablesDB.listRows()` | Deprecated API |
| `ColumnString` | `ColumnVarchar` or `ColumnText` | `string` deprecated |
| Derived/custom resource ID, or fresh `ID.unique()` per retry | Preallocate one `ID.unique()`, persist, reuse | Leakage/collision, or duplicate resource |
| N+1 relationship fetches | `Query.select(['col', 'relation.col'])` | Kills extra round-trips |
| Read-modify-write | `Operator.increment()` | Race condition |
| Large offsets | `Query.cursorAfter(id)` | O(n) vs O(1) |
| Fetching totals by default | `total: false` | Kills COUNT scan |
| Missing indexes | Index every queried/ordered column | Full table scan |
| Full re-fetch every sync | `Query.updatedAfter()` + per-table timestamps | Wastes bandwidth |
| Loop with per-row create/update/delete | Matching bulk call | N requests + N transaction ops vs 1 |
| Treating bulk as partial-success | One bulk request is atomic; reconcile exact postcondition | Appwrite bulk is all-or-nothing per request |
| Empty bulk update/delete queries | Reject unless an explicit all-rows operation is authorized | Empty queries target every row |
| SDK init inside handler | Init outside for warm reuse | Repeated setup per call |
| Polling | Realtime or event triggers | Wasted executions |
| Client-side event filtering | Realtime queries | Server does the work |
| Raw channel strings | `Channel` helpers | Typos, no autocomplete |
| Hand-written types | `appwrite generate` | Schema drift, no autocomplete |
| Durable rows + cleanup cron for online/typing state | Presences API | Ephemeral state does not belong in a table |
| Hardcoded secrets | Env vars / secret manager | Security risk |
| One function per operation | One function per domain | Cold starts, deploy sprawl |

## Resources

Docs <https://appwrite.io/docs> · API <https://appwrite.io/docs/references> · SDKs <https://github.com/appwrite>
