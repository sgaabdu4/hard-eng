# Issue tracker: GitLab

Tracker cards for this repo live as GitLab issues. Use the [`glab`](https://gitlab.com/gitlab-org/cli) CLI for all operations.

## Conventions

- **Create an issue**: `glab issue create --title "..." --description "..."`. Use a heredoc for multi-line descriptions. Pass `--description -` to open an editor
- **Read an issue**: `glab issue view <number> --comments`. Use `-F json` for machine-readable output
- **List issues**: `glab issue list -F json` with appropriate `--label` filters
- **Comment on an issue**: `glab issue note <number> --message "..."`. GitLab calls comments "notes"
- **Apply / remove labels**: `glab issue update <number> --label "..."` / `--unlabel "..."`. Multiple labels can be comma-separated or by repeating the flag
- **Close**: `glab issue close <number>`. `glab issue close` does not accept a closing comment, so post the explanation first with `glab issue note <number> --message "..."`, then close
- **Merge requests**: GitLab calls PRs "merge requests". Use `glab mr create`, `glab mr view`, `glab mr note`, etc. — the same shape as `gh pr ...` with `mr` in place of `pr` and `note`/`--message` in place of `comment`/`--body`

Infer the repo from `git remote -v` — `glab` does this automatically when run inside a clone.

## Merge requests as a triage surface

**MRs as a request surface: no.** _(Set to `yes` if this repo treats external merge requests as feature requests; `/triage` reads this flag.)_

When set to `yes`, MRs run through the same labels and states as issues, using the `glab mr` equivalents:

- **Read an MR**: `glab mr view <number> --comments` and `glab mr diff <number>` for the diff
- **List external MRs for triage**: `glab mr list -F json`, then keep only MRs whose author is not a project member/owner (a contributor's MR, not a maintainer's in-flight work)
- **Comment / label / close**: `glab mr note`, `glab mr update --label`/`--unlabel`, `glab mr close`

Unlike GitHub, GitLab numbers issues and MRs separately, so `#42` is unambiguous once you know which surface the maintainer means.

## When a skill says "publish to the issue tracker"

Only an explicit user request to publish accepted plan slices authorizes issue
creation. Create a GitLab issue that links to the source plan and slice;
`plan.md` remains canonical.

## When a skill says "fetch the relevant ticket"

Run `glab issue view <number> --comments`.

## Optional planning map operations

Use only when the user explicitly asks to publish an accepted `plan.md` as a
tracker map. The **map** and **child** issues are execution views; `plan.md`
remains canonical.

- **Map**: a single issue labelled `planning:map`, linking the source plan and indexing its published cards. `glab issue create --label planning:map`. (On GitLab tiers with native epics, an epic may hold the map instead; a labelled issue works everywhere.)
- **Child ticket**: an issue carrying `Part of #<map>` at the top of its description and labels `planning:<type>` (`research`/`prototype`/`alignment`/`task`). Once claimed, the ticket is assigned to the driving dev
- **Blocking**: GitLab's **native blocking link** — the canonical, UI-visible representation. Add it with the `/blocked_by #<n>` quick action, posted as a note (`glab issue note <child> --message "/blocked_by #<blocker>"`). Native blocking links are a Premium/Ultimate feature; on the free tier (or where unavailable) fall back to a `Blocked by: #<n>, #<n>` line at the top of the description. A ticket is unblocked when every blocker is closed
- **Frontier query**: `glab issue list -F json` scoped to the map's children, drop any with an open blocker — a native `blocked_by` link to an open issue (`glab api projects/:id/issues/:iid/links`), or an open issue in the `Blocked by` line — or an assignee; first in map order wins
- **Claim**: `glab issue update <n> --assignee @me` — the session's first write
- **Resolve**: `glab issue note <n> --message "<answer>"`, then `glab issue close <n>`, then update the source plan traceability and map execution status
