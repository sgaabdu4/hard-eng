# Browser Release Credential Bootstrap

- Trigger = explicit request to create/transfer Sentry release credentials through Browser; implicit browser use = forbidden.
- Browser surface = `browser:control-in-app-browser`; read and follow it before UI work.
- Owner = token creation + GitHub environment secret transport; Sentry issue/release reads/writes = installed `sentry` CLI.

## Target

| Input | Placeholder | Proof |
|---|---|---|
| Sentry target | `<sentry-org>/<sentry-project>` | Project page + signed-in organization |
| GitHub target | `<github-owner>/<github-repo>` | Repository settings |
| GitHub environment | `<github-environment>` | Exact environment configuration page |
| Secret name | `SENTRY_AUTH_TOKEN` | Workflow `secrets.SENTRY_AUTH_TOKEN` + secret list name |

- Account, organization, project, repository, and environment mismatch → stop + ask.
- Existing same-name secret → inspect name only; overwrite/revoke → explicit replacement approval.

## Workflow

1. Verify exact Sentry + GitHub targets and authenticated account → continue only on match.
2. Sentry User Settings → API → Personal Tokens → Create New Token.
3. Name = `<service>-release-ci`; Release = `Admin`; all unrelated permission groups = `No Access` → preview = `project:releases`.
4. Create token → click `Copy to clipboard`; never call clipboard read, print, paste into shell, or expose the value.
5. GitHub exact environment → Add environment secret → name = `SENTRY_AUTH_TOKEN` → paste directly into Value → submit.
6. Verify the environment secret list contains `SENTRY_AUTH_TOKEN` only → close/confirm the one-time token view.

## Completion

| Gate | PASS proof |
|---|---|
| Candidate | Sentry token preview = `project:releases` |
| External write | Exact GitHub environment lists `SENTRY_AUTH_TOKEN` |
| Consumer preflight | CI references `secrets.SENTRY_AUTH_TOKEN` for release create/set-commits/deploy/finalize |
| Live binding | Successful production CI deploy → release/deploy record read through `sentry` |

- DSN = public event-ingest identifier; never substitute it for `SENTRY_AUTH_TOKEN`.
- Browser unavailable/auth blocked/target changed → stop + report; do not use guessed URLs or alternate credentials.
