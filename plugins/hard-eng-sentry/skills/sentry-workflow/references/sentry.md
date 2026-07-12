# Sentry

Classify the request as issue/event diagnosis, SDK setup or upgrade,
instrumentation, alerts, OpenTelemetry, AI monitoring, release/sourcemaps, or
PR feedback. Verify organization, project, environment, release, platform, and
current official Sentry docs before mutation.

Read the exact issue/event, stack, breadcrumbs, tags, and relevant source
owner before diagnosing. Keep auth in approved environment/config; never print
tokens. Prefer the connected API or installed CLI, use read-only calls first,
and require approval for settings, alerts, releases, or production changes.

Fix root source behavior, not only grouping or noise. Prove setup with a
controlled test event and source mapping, diagnosis with the affected test and
event evidence, and alerts/instrumentation with current configuration readback.
Do not create multiple Sentry routers or run semantic review automatically.
