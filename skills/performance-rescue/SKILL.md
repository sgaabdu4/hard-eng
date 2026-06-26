---
name: performance-rescue
description: Use for slowness, latency, p50/p95, efficiency, benchmarks, or making apps, APIs, queries, or UI faster.
---

# Performance Rescue

No guesswork. Measure the exact slow path, fix the real bottleneck with the smallest safe change, then remeasure the same path.

## First Moves

1. Load relevant stack skills: React/Next, Appwrite, Flutter/Dart, tests, browser verification.
2. Name the workflow: `production performance smoke test`.
3. Capture target route/action/API, role/test account, env, and what "slow" means.
4. Measure before editing. If telemetry is missing, add tiny scoped instrumentation.

## Metrics

Always report:

```text
route/action:
sample size:
status counts:
p50/p75/p95/p99/max:
error rate:
saturation:
slowest phase:
before vs after:
remaining risk:
```

Use client-visible timing plus backend/service timing. Do not summarize latency with only averages or p50.

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

## Details

Read `references/runbook.md` for instrumentation patterns, Appwrite/cloud-function checks, browser/Core Web Vitals gates, test ideas, red flags, and final report format.

## Final

Include exact before/after metrics, code/data-flow changes, verification commands, production/browser evidence, and any remaining bottleneck.
