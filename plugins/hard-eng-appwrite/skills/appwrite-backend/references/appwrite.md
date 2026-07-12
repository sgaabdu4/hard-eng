# Appwrite

Identify Cloud versus self-hosted version, client versus server execution,
official SDK owner, database/table/bucket/function IDs, permission model,
indexes, migration/rollback path, and test environment before changing code.
Verify unstable SDK signatures and platform behavior in current official docs.

Use official SDKs unless an endpoint is genuinely unavailable and an isolated,
tested low-level call is required. Default permissions deny; never broaden
`any` write access casually. Prefer selected fields, cursor pagination,
indexed query columns, atomic operators or transactions over read-modify-write,
Realtime over polling, SDK-managed uploads, and SDK initialization outside
function handlers.

Schema, index, permission, retention, auth, destructive, or production-data
changes require Plan and explicit approval. Keep secrets in approved runtime
configuration and never print them. Prove emulator/test-project behavior,
idempotency, concurrency, permission denials, rollback, Realtime observers,
and function retry/error paths as applicable.
