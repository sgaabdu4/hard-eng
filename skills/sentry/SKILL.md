---
name: sentry
description: Sentry CLI issue remediation. Use when Codex must investigate, fix, or verify a Sentry issue through the installed `sentry` executable.
---

# Sentry

## Contract

- Transport = installed `sentry` CLI only; `sentry-cli` + MCP + browser = forbidden.
- Scope = issue remediation; release/artifact/dashboard/project administration = not owned.
- Sentry data = runtime evidence; Seer output = hypothesis; repository/runtime proof decides root cause.
- Read = allowed within user scope; resolve/unresolve/archive/merge/API write = external mutation → exact approval.
- Secret = stored CLI auth only; `--show-token` + token output/arguments/logging = forbidden.
- Large JSON → bounded fields + Context Mode; raw dump = forbidden.

## Admission

| Gate | Proof |
|---|---|
| Executable | `command -v sentry` + `sentry --version` |
| Current syntax | `sentry <command> --help`; never rely on memorized alpha syntax |
| Identity | `sentry auth status --fresh` + `sentry auth whoami --fresh` |
| Target | explicit `<org>/<project>`; auto-detect only when one project is proven |
| Scope | issue IDs/query + environment + explicit time window; `all` also requires complete pagination |

- Missing executable/auth/target/scope → report exact blocker; never switch transport.

## Route

| Need | Command/evidence | Complete |
|---|---|---|
| Inventory | `sentry issue list <org/project> --query 'is:unresolved <filters>' --period <window> --fresh --json --fields id,shortId,title,count,userCount,lastSeen,status,project,priority,isUnhandled` | Declared window + every cursor exhausted + stable issue inventory |
| Inspect | `sentry issue view <issue> --fresh --json --fields id,shortId,title,culprit,count,userCount,firstSeen,lastSeen,status,project,metadata,event,trace,replayIds` | Latest event + stack/context + affected release/environment/user scope captured |
| Compare events | `sentry issue events <issue> --period <window> --fresh --json --fields eventID,title,location,culprit,dateCreated` → selected representative event with `--full` | Variants, recurrence boundary, first/last relevant event, and counterexample checked |
| Correlate | Returned trace/replay IDs → `sentry trace view ... --full --fresh --json`; `sentry log list <trace-id> --fresh --json`; `sentry replay view ... --fresh --json` | Only decision-relevant linked evidence retained |
| Seer | Explicit user request only → `sentry issue explain <issue>` or `sentry issue plan <issue>` | Output labeled hypothesis + independently verified |
| Fix | Root-cause + owned-blast-radius repair; stack-specific reproduction/regression gates | Candidate proof covers reproduction + regression + affected boundaries |
| Verify production | Identify deployed release/commit → refresh issue/events after observation window | No recurrence claim includes window + traffic evidence; otherwise status = awaiting runtime proof |
| Resolve | Approved deployed candidate → `sentry issue resolve <issue> --in <release|@commit|@next>`; fresh view proves result | Resolution target + resulting status verified |

- Multiple issues → batch only by verified shared root cause; retain proof/status per issue ID.
- CLI/API/Seer claim conflicting with source/runtime evidence → preserve conflict + investigate; never average claims.
- Failed command → capture bounded stderr + exit code → diagnose once with `--help`; no unchanged retry.

## Output

| ID | Impact | Runtime evidence | Root owner/cause | Fix/proof | Runtime status |
|---|---|---|---|---|---|

- Completion = every scoped ID fixed, explicitly deferred, or blocked with owner/next proof.
- `PASS` requires local gates + no unresolved scoped blocker; production-resolution claim additionally requires deployed observation evidence.
