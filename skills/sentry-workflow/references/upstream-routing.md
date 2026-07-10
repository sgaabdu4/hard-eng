# Sentry Upstream Routing

Use only the matching pinned source. Treat every source as read-only.

| Intent | Pinned source |
| --- | --- |
| CLI, API calls, authentication, organizations, projects, issues, or events | `vendor/skill-upstreams/sentry-cli/plugins/sentry-cli/skills/sentry-cli/SKILL.md` |
| SDK installation or basic error monitoring | `vendor/skill-upstreams/sentry-for-ai/skills/sentry-sdk-setup/SKILL.md` |
| Alerts, OpenTelemetry, span streaming, snapshots, or AI monitoring | `vendor/skill-upstreams/sentry-for-ai/skills/sentry-feature-setup/SKILL.md` |
| Production issue diagnosis, exception repair, or Sentry-backed PR review | `vendor/skill-upstreams/sentry-for-ai/skills/sentry-workflow/SKILL.md` |

The wrapper owns the route and user-facing handoff. The selected upstream skill
owns its detailed operating guidance.
