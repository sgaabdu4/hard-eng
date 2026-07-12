---
name: sentry-workflow
description: Use for any Sentry issue, event, SDK, CLI/API, instrumentation, alert, OpenTelemetry, AI monitoring, release, sourcemap, or Sentry PR-review task. Route every Sentry request through this one skill.
---

# Sentry workflow

Read [sentry.md](references/sentry.md) and select only the matching task
boundary. Do not invoke overlapping Sentry skills.

Use connected/installed Sentry surfaces when available. Authentication,
organization/project selection, production changes, alerts, releases, and
instrumentation remain explicit approval boundaries. Never expose tokens or
invent issue/event evidence.
