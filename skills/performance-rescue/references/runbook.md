# Performance Runbook

## Measurement Sources

- Direct API sample: 5-20 exact-route requests with cache busting/no-store
- Production logs/traces: p50/p75/p95/p99/max, phase timings, status/error counts
- Browser smoke: exact page/action, visible content, action-to-confirmation timing
- Saturation: CPU, memory, queue, DB pool, connection count, concurrency, request rate
- Web vitals when page UX matters: LCP <= 2500 ms, INP <= 200 ms, CLS <= 0.1 at p75

## Diagnostic Gates

- Compare browser/client total with backend service time
- Use request ids across browser, route handler, function, DB, and external APIs
- Use Chrome/React profiler only when render/main-thread work is suspected
- Use a small load smoke for backend regressions before broad load tests
- Add bundle/page budgets only when bytes or third parties are implicated

## Instrumentation

Use existing telemetry first. If missing, add compact structured metrics:

- route/action
- user/env type
- total ms and phase timings
- key counts/sizes
- status/ok/error class
- request id

Do not log secrets, tokens, emails, names, raw payloads, prompts, or PII. Prefer `Server-Timing`, User Timing, `node:perf_hooks`, or OpenTelemetry spans when already present.

## Appwrite / DB

- Use official SDK and TablesDB where applicable
- Use `Query.select()` on hot queries
- Check indexes before blaming code
- Avoid offset pagination and unbounded relationship hydration
- Treat invalid projections and selected-field drift as production 500 risks

## Cloud Functions / Mutations

- Identify write authority before editing
- Keep side effects in the canonical handler/service
- Measure function execution separately from route overhead
- Split cold start/init from warm execution
- Reuse clients/connections outside handlers only when runtime reuse is safe
- For button latency, show optimistic/disabled/pending state only if business rules allow

## Tests

Prefer tests that prove behavior:

- starts independent work before awaiting slow core data
- reuses lookup rows instead of refetching
- does not block primary response on optional timeout
- does not retry non-idempotent writes
- uses fake timers for timeout/retry behavior

## Red Flags

- "Fast now" without p50/p75/p95/p99/max
- Hiding errors, saturation, max, or outliers
- Caching mutable state without invalidation
- Retrying writes
- Optimizing UI before proving backend/network/render cause
- Treating local dev timing as production proof
