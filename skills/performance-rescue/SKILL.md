---
name: performance-rescue
description: Use for slowness, latency, p50/p95, efficiency, benchmarks, or making apps, APIs, queries, or UI faster.
---

# Performance Rescue

No guesswork. Measure the exact slow path, fix the real bottleneck with the smallest safe change, then remeasure the same path.

## First Moves

Read `references/workflow.md` before measuring or fixing performance.

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

## Details

Read `references/runbook.md` for instrumentation patterns, Appwrite/cloud-function checks, browser/Core Web Vitals gates, test ideas, red flags, and final report format.

## Final

Include exact before/after metrics, code/data-flow changes, verification commands, production/browser evidence, and any remaining bottleneck.
