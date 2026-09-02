# Tracker Adapter

## Authority
- Local ticket files = the only source of truth; the tracker is a push-mirror, best-effort, never authoritative. Remote carries no CAS token, no flock, no session digests, no receipt gating: no claim-safety invariant is computable from an issue, so the adapter must work offline and never blocks or reverts a local transition.

## Ops
- Exactly four: `create-ticket` (returns `tracker_ref`), `update-status`, `close-ticket`, `link-pr`. No adapter grows a fifth op.
- Decompose → `create-ticket` per new ticket. Additive lane (`--amend`) → `create-ticket` per new ticket only. Outcome/risk lane (`--reconcile`) → `close-ticket` (note: "cancelled: superseded by replan") per cancelled ticket + `create-ticket` per replacement. Ship → `update-status` + `link-pr` + `close-ticket`.
- Invocation = a post-transition hook inside `ticket_state.py`, best-effort: warns on failure, never blocks or reverts the local transition it's attached to.

## Sync + Pull
- `sync-tracker` = manual reconcile; diffs local state against every `tracker_ref` and replays the full local truth, so a missed or failed hook call self-heals on the next run. Epic terminal close runs a `sync-tracker` close-all pass across every ticket.
- `sync-tracker --pull` = report-only: lists remote deltas (issue closed/reopened remotely, new issues labeled for the epic, comments requesting changes) as a drift report; it never auto-applies anything. Auto-apply is forbidden twice over: the remote carries none of the claim-safety evidence (no CAS/session digests/fingerprints), and issue text is written by anyone, so untrusted content must never drive agent actions directly.
- A session (or the user) turns a real inbound request into the matching local move: additive → `--amend`; cancellation/outcome change → the mid-build replan lane; noise → ignore and let the next `sync-tracker` re-push local truth.

## Config
- Optional `"tracker"` key in the repo's gates manifest (`hard-eng.gates.json`); extra top-level keys are inert to the validator, so the key is additive only. Missing key = no tracker wired, every op is a no-op.

```json
{"tracker": {"adapter": "github", "repository": "owner/name", "project": null}}
```

## Credentials + Probe
- Names = `GITHUB_REPOSITORY` (GitHub; auth = `gh auth status`), `JIRA_SITE` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `JIRA_PROJECT` (Jira Cloud; Basic `email:token`), `AZDO_ORG` + `AZDO_PROJECT` + `AZDO_PAT` (Azure DevOps; Basic `:PAT`); read from the process environment, then the checkout's ignored `.env`; `probe-trackers --write-env-example` appends the Jira/Azure names to `.env.example` inside `# >>> hard-eng trackers >>>` markers so feature setup offers `.env`.
- `plan_state.py probe-trackers` = one authenticated read per adapter (`gh auth status`, Jira `GET /rest/api/3/myself`, Azure `GET _apis/projects/<project>?api-version=7.1`) → `probes` in `plan-steps.json` + `tracker_N`, `tracker_N_available`, `tracker_N_detail` lines; token values + their base64 forms are redacted from every line; `record-step closing` with `tickets=<adapter>` refuses unless that adapter's probe is `available`.

## Adapters
- First adapter = `tracker_github.py`, via the sanctioned `gh` CLI (`gh issue create|edit|close`).
- `project` (GitHub Projects) needs an extra `gh` auth scope beyond issues; the adapter probes for it and degrades to issues-only with a warning when absent, never hard-failing the ticket transition over a missing project scope.
- Jira, Azure DevOps = future adapters behind the identical four ops + `--pull`; only the vendor-specific implementation changes, never the contract.
