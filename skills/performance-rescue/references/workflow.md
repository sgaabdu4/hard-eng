# Performance Rescue Workflow

## First Moves

1. Load relevant stack skills: React/Next, Appwrite, Flutter/Dart, tests, and browser verification.
2. Name the workflow: `production performance smoke test`.
3. Capture target route/action/API, role/test account, env, and what "slow" means.
4. Measure before editing. If telemetry is missing, add tiny scoped instrumentation.

## Fix Order

1. Delete unnecessary work.
2. Kill waterfalls; start independent work early and await late.
3. Reuse fetched rows/maps/lookups.
4. Reduce DB cost: projection, indexes, cursor pagination, bounded queries.
5. Defer optional enrichment; return primary data first.
6. Reduce render/main-thread work only after profiler evidence.
7. Add timeout/retry only for proven idempotent reads.
8. Cache only after correctness and invalidation are clear.

Keep write authority in the canonical owner; do not move lifecycle or side effects into a faster-looking caller.
