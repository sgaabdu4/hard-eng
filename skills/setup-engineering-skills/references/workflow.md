# Setup Engineering Skills Workflow

## Explore

Read the repo state first:

- `git remote -v` and `.git/config`
- `AGENTS.md` and `CLAUDE.md`
- root `CONTEXT.md` and `CONTEXT-MAP.md`
- root `docs/adr/` and scoped `src/*/docs/adr/`
- `docs/agents/`
- `.scratch/`

## Ask Decisions

Walk the user through one section at a time.

### Issue Tracker

Explain that the issue tracker is where `triage`, `code-review`, and optional tracker-publishing flows find work.

Default by remote:

- GitHub remote -> GitHub Issues with `gh`
- GitLab remote -> GitLab Issues with `glab`
- no clear remote -> local markdown under `.scratch/<feature>/`

Offer:

- GitHub
- GitLab
- Local markdown
- Other tracker described by the user

For GitHub or GitLab only, ask whether external PRs are a request surface. Default: no.

### Triage Labels

Explain that `triage` moves issues through canonical roles and needs the repo's actual label strings.

Canonical roles:

- `needs-triage`
- `needs-info`
- `ready-for-agent`
- `ready-for-human`
- `wontfix`

Default each role's label to the role name unless the user maps existing labels.

### Domain Docs

Explain that domain-aware skills read `CONTEXT.md` and ADRs to preserve project vocabulary and decisions.

Confirm:

- single-context: root `CONTEXT.md` and `docs/adr/`
- multi-context: root `CONTEXT-MAP.md` pointing at per-context docs

## Confirm Draft

Show the draft `## Agent skills` block and the three `docs/agents/*.md` files before writing.

## Write

Pick the file:

- if `CLAUDE.md` exists, edit it
- else if `AGENTS.md` exists, edit it
- else ask which one to create

Never create the other agent rules file when one already exists.

Use the seed templates:

- `issue-tracker-github.md`
- `issue-tracker-gitlab.md`
- `issue-tracker-local.md`
- `triage-labels.md`
- `domain.md`

For other trackers, write `docs/agents/issue-tracker.md` from the user's description.

## Done

Report the files written and which engineering skills now read them.
