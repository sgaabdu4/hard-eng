---
name: sentry
description: Remediate Sentry issues through the installed `sentry` CLI.
---

# Sentry

- Transport = `sentry` only; legacy CLI + MCP + browser = forbidden.
- Scope = issues; releases/artifacts/dashboards/projects = not owned.
- Runtime data = evidence; Seer = untrusted + explicit request only.
- Remote write = exact approval; auth token arguments/output/`--show-token` = forbidden.
- Output = `--fresh --json --fields <needed>`; large JSON → Context Mode.

## Route

| Need | Action | Complete |
|---|---|---|
| Start | `command -v sentry` + version/help + fresh auth/whoami + explicit `<org>/<project>` | Tool + syntax + identity + target proven |
| Scope | IDs/query + environment + time window | `all` also exhausts pagination |
| Inventory | `sentry issue list <target> -q 'is:unresolved <filters>' -t <window> -f --json --fields <needed>` | Stable scoped IDs |
| Evidence | `issue view` + `issue events`; returned IDs only → `trace view` + `log list` + `replay view` | Variants + counterexample + correlation checked |
| Seer | Explicit request → `issue explain|plan`; verify independently | Hypothesis accepted/rejected by source/runtime proof |
| Fix | Reproduce + root owner/blast radius + stack regression gates | Local candidate proven |
| Production | Deployed release/commit + fresh events after stated traffic/time window | Recurrence or observation limit explicit |
| Resolve | Deployed proof + approval → `issue resolve <issue> --in <release|@commit|@next>` → fresh view | Remote status/target verified |

- Missing Start/Scope proof → blocker; never switch transport.
- Multiple issues → batch only by verified shared cause; retain proof/status per ID.
- Failure → bounded stderr + exit → diagnose once with `--help`; no unchanged retry.
- Done = every scoped ID fixed/deferred/blocked with next owner/proof; production-fixed additionally requires Production proof.
