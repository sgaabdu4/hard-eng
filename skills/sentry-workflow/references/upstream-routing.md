# Sentry Upstream Routing

Use only the matching pinned source. Treat every source as read-only.

| Exact intent | Pinned source |
| --- | --- |
| Sentry CLI commands, CLI authentication, releases, deploys, artifacts, debug files, or sourcemaps | `../../../vendor/skill-upstreams/sentry-cli/plugins/sentry-cli/skills/sentry-cli/SKILL.md` |
| Resolve line-specific review comments authored by `sentry[bot]` | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-code-review/SKILL.md` |
| Create alerts, notification actions, priority rules, or workflow automations | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-create-alert/SKILL.md` |
| Diagnose and fix a known production issue from its Sentry link, ID, event, stack, trace, breadcrumbs, or logs | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-debug-issue/SKILL.md` |
| Choose among alerts, AI monitoring, OTel exporter, or Cocoa snapshots when the requested advanced feature is still unclear | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-feature-setup/SKILL.md` |
| Orient an existing setup or provision a new project with first-error SDK setup and end-to-end telemetry proof | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-get-started/SKILL.md` |
| Add or change SDK instrumentation for errors, traces, logging, metrics, profiling, replay, user feedback, cron, or streamed spans | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-instrument/SKILL.md` |
| Configure an OpenTelemetry Collector with the Sentry Exporter, multi-project routing, or automatic project creation | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-otel-exporter-setup/SKILL.md` |
| Review or fix Seer Bug Prediction findings on pull requests | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-pr-code-review/SKILL.md` |
| Upgrade the Sentry JavaScript SDK across major versions or repair deprecated/breaking APIs | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-sdk-upgrade/SKILL.md` |
| Instrument AI/LLM calls, agents, conversations, token use, or supported AI SDKs | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-setup-ai-monitoring/SKILL.md` |
| Configure Apple/Cocoa Sentry Snapshots, SnapshotPreviews, snapshot uploads, or snapshot CI | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-snapshots-cocoa/SKILL.md` |
| Choose among production debugging, Sentry-bot review, Seer review, or SDK upgrade when the workflow is still unclear | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-workflow/SKILL.md` |

The wrapper owns the route and user-facing handoff. The selected upstream skill
owns its detailed operating guidance. When more than one row still matches, ask
one targeted question and do not load multiple upstream skills speculatively.
