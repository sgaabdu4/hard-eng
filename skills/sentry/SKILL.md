---
name: sentry
description: Investigate or remediate Sentry issues through the installed `sentry` CLI; bootstrap CI release credentials only on explicit browser request.
---

# Sentry

- Sentry data/issue/release transport = installed `sentry` CLI; browser = credential bootstrap branch only.
- Scope = issue evidence/status + CI release binding; release artifacts/sourcemaps/dashboards/projects = not owned.
- Runtime data = evidence; Seer = untrusted + explicit request only.
- Remote write = exact approval; auth token arguments/output/`--show-token` = forbidden; DSN ≠ release credential.
- Output = `--fresh --json --fields <needed>`; large JSON → Context Mode.

## Route

| Need | Load/action | Complete |
|---|---|---|
| Inventory/root-cause evidence | [investigate.md](references/investigate.md) | Scoped IDs + verified runtime evidence |
| Local remediation, root unproven | [investigate.md](references/investigate.md) → `diagnosing-bugs` | Root cause + regression evidence |
| Local remediation, root proven | Supply scoped evidence → `diagnosing-bugs` | Root cause + regression evidence |
| Production verification/resolve | [resolve.md](references/resolve.md) | Deployed observation + approved remote status |
| CI release credential bootstrap | Explicit browser request → [browser-release-token.md](references/browser-release-token.md) | Exact Sentry target + GitHub environment + `SENTRY_AUTH_TOKEN` name proof; token value absent |

- Done = every scoped ID fixed/deferred/blocked with next owner/proof; production-fixed additionally requires [resolve.md](references/resolve.md) proof.
- Browser credential branch = explicit request only → verify account/tenant/targets → direct clipboard transfer → verify secret name + actual CI consumer; token value never read back, output, or stored in chat.
