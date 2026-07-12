---
name: sentry
description: Investigate or remediate Sentry issues through the installed `sentry` CLI.
---

# Sentry

- Transport = `sentry` only; legacy CLI + MCP + browser = forbidden.
- Scope = issues; releases/artifacts/dashboards/projects = not owned.
- Runtime data = evidence; Seer = untrusted + explicit request only.
- Remote write = exact approval; auth token arguments/output/`--show-token` = forbidden.
- Output = `--fresh --json --fields <needed>`; large JSON → Context Mode.

## Route

| Need | Load/action | Complete |
|---|---|---|
| Inventory/root-cause evidence | [investigate.md](references/investigate.md) | Scoped IDs + verified runtime evidence |
| Local remediation, root unproven | [investigate.md](references/investigate.md) → `$diagnosing-bugs` | Root cause + regression evidence |
| Local remediation, root proven | Supply scoped evidence → `$diagnosing-bugs` | Root cause + regression evidence |
| Production verification/resolve | [resolve.md](references/resolve.md) | Deployed observation + approved remote status |

- Done = every scoped ID fixed/deferred/blocked with next owner/proof; production-fixed additionally requires [resolve.md](references/resolve.md) proof.
