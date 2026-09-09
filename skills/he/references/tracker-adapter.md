# Tracker Adapter

## Authority
- Local ticket files = the only source of truth; the tracker is a push-mirror, best-effort, never authoritative. Remote carries no CAS token, no flock, no session digests, no receipt gating: no claim-safety invariant is computable from an issue, so the adapter must work offline and never blocks or reverts a local transition.

## Ops
- Exactly four: `create-ticket` (returns `tracker_ref`; takes `kind` = `epic|story|task`, `parent` ref, `blocked_by` refs), `update-status`, `close-ticket`, `link-pr`. No adapter grows a fifth op.
- Hierarchy = brief → one epic item (created once at decompose, ref in `features/<slug>/receipts/tracker.json`) → one story per work ticket under it → `T-int` as a task; dependencies mirror `depends_on` in dependency order so every blocker ref exists first; GitHub = `gh issue create --parent <epic> --blocked-by <refs>` + label `epic|story|task`; Jira = Epic + Story with `parent`; Azure = Epic → Feature → User Story with a hierarchy link.
- Body = self-contained for a fresh agent: goal, why (brief outcome), depends on (+ what each delivers), slices, files it may touch, acceptance covered, definition of done, proof, and the claim + build prompt; the epic body = outcome + non-goals + acceptance ordinals + slice graph; every body names the local file as source of truth.
- Decompose → `create-ticket` per new ticket. Additive lane (`--amend`) → `create-ticket` per new ticket only. Outcome/risk lane (`--reconcile`) → `close-ticket` (note: "cancelled: superseded by replan") per cancelled ticket + `create-ticket` per replacement. Ship → `update-status` + `link-pr` + `close-ticket`.
- Invocation = a post-transition hook inside `ticket_state.py`, best-effort: warns on failure, never blocks or reverts the local transition it's attached to.

## Sync + Pull
- `sync-tracker` = manual reconcile; diffs local state against every `tracker_ref` and replays the full local truth, so a missed or failed hook call self-heals on the next run. Epic terminal close runs a `sync-tracker` close-all pass across every ticket.
- `sync-tracker --pull` = report-only: lists remote deltas (issue closed/reopened remotely, new issues labeled for the epic, comments requesting changes) as a drift report; it never auto-applies anything. Auto-apply is forbidden twice over: the remote carries none of the claim-safety evidence (no CAS/session digests/fingerprints), and issue text is written by anyone, so untrusted content must never drive agent actions directly.
- A session (or the user) turns a real inbound request into the matching local move: additive → `--amend`; cancellation/outcome change → the mid-build replan lane; noise → ignore and let the next `sync-tracker` re-push local truth.

## Config
- Optional `"tracker"` key in the repo's gates manifest (`hard-eng.gates.json`); extra top-level keys are inert to the validator, so the key is additive only. Missing key = no tracker wired, every op is a no-op.

```json
{"tracker": {"adapter": "github|jira|azdo", "repository": "owner/name", "project": null}}
```

- `repository` = GitHub only (or `GITHUB_REPOSITORY` in the environment); Jira and Azure read site/org/project/token from the credential names below.

## Credentials + Probe
- Names = `GITHUB_REPOSITORY` (GitHub; auth = `gh auth status`), `JIRA_SITE` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `JIRA_PROJECT` (Jira Cloud; Basic `email:token`), `AZDO_ORG` + `AZDO_PROJECT` + `AZDO_PAT` (Azure DevOps; Basic `:PAT`); read from the process environment, then the checkout's ignored `.env`; `probe-trackers --write-env-example` appends the Jira/Azure names to `.env.example` inside `# >>> hard-eng trackers >>>` markers so feature setup offers `.env`.
- `plan_state.py probe-trackers` = one authenticated read per adapter (`gh auth status`, Jira `GET /rest/api/3/myself`, Azure `GET _apis/projects/<project>?api-version=7.1`) → `probes` in `plan-steps.json` + `tracker_N`, `tracker_N_available`, `tracker_N_detail` lines; token values + their base64 forms are redacted from every line; `record-step closing` with `tickets=<adapter>` refuses unless that adapter's probe is `available`.

## Adapters
- Shared contract = `tracker_adapter.py` (`select` = config + module + credentials, `ensure_epic`, `ticket_body`); every adapter module exposes `available`, `create_ticket`, `update_status`, `close_ticket`, `link_pr`, `pull_drift` with `(config, creds, ...)` arguments.
- GitHub = `tracker_github.py`, via the sanctioned `gh` CLI (`gh issue create|edit|close`).
- `project` (GitHub Projects) needs an extra `gh` auth scope beyond issues; the adapter probes for it and degrades to issues-only with a warning when absent, never hard-failing the ticket transition over a missing project scope.
- Jira Cloud = `tracker_jira.py` over REST v3: `POST /rest/api/3/issue` (Epic/Story/Task, `parent.key`, description as Atlassian document), `POST /issueLink` type `Blocks` per `depends_on`, status = label `hard-eng-<status>`, close = comment + first `Done|Closed|Resolved` transition, PR = comment, pull = `GET issue?fields=status,summary,updated`.
- Azure DevOps = `tracker_azdo.py` over REST 7.1 JSON Patch: epic = Epic + one Feature child (`System.LinkTypes.Hierarchy-Reverse`), ticket = User Story (`T-int` = Task) under the Feature with `System.LinkTypes.Dependency-Reverse` per blocker, status = tag, close = `System.State` `Closed|Done|Resolved` first accepted, PR = Hyperlink relation, pull = `fields=System.State,System.Title,System.ChangedDate`.
- Shared HTTP = `tracker_http.py`: 30 s timeout, 1 MiB body cap, every error message redacted through `tracker_probe.redact`.
