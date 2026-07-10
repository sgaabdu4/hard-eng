# Issue tracker: Local Markdown

Local tracker cards for this repo live as markdown files in `.scratch/`.
The canonical plan remains `docs/planning/<feature-slug>/plan.md`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- Tracker cards link to the canonical `docs/planning/<feature-slug>/plan.md` and slice id
- Implementation issues are `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Only an explicit request to publish accepted plan slices authorizes creation.
Create a new issue file under `.scratch/<feature-slug>/issues/` and keep
`plan.md` canonical.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Optional planning map operations

Use only when the user explicitly asks to publish an accepted `plan.md` as a
tracker map. The **map** and **child** files are execution views of the
canonical plan.

- **Map**: `.scratch/<effort>/map.md` — links to the source plan and indexes its published cards
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the accepted slice task in the body. A `Type:` line records the ticket type (`research`/`prototype`/`alignment`/`task`); a `Status:` line records `claimed`/`resolved`
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins
- **Claim**: set `Status: claimed` and save before any work
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then update the source plan traceability and map execution status
