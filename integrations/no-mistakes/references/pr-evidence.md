# PR Evidence Repair

Use this before finalizing any no-mistakes run that opened or updated a PR.

## Required result

- PR description contains actual GitHub links, not machine-local paths
- UI work has screenshots when the run captured them
- UI or phone E2E has a reviewer-openable 2x video link, or the evidence table
  stays open until one is attached.
- Screenshots are GitHub `user-attachments` URLs or another reviewer-openable
  URL, never committed evidence files.
- Screenshot and required video evidence are tracked in the issue-status table
  as resolved, missing, unhosted, or upload-failed.
- Existing pipeline sections stay in place; append the managed evidence section
  after the current PR body.
- Managed evidence includes `Current head: <sha>` so the
  `no-mistakes-required` check can prove it matches the PR head being reviewed.
- If `no-mistakes axi status` is unavailable, PR evidence repair falls back to
  the PR body `git push no-mistakes` pipeline section only when every summary is
  passed or auto-fixed, push completion is recorded, and that pipeline section
  proves the current head before the managed evidence block.
- If that fallback stays Open because the pipeline section lacks current-head
  proof, do not convert it into managed passed evidence. Re-verify the PR head
  locally, then add a maintainer-owned PR comment or review with `Current head:
  <sha>` plus `outcome: checks-passed` or `No open no-mistakes findings`.
- Outside the managed PR body block, the required check accepts only a
  maintainer-owned PR comment or review that includes the current head SHA and
  a passed marker, except same-repo maintainer PRs that only update
  `vendor/skill-upstreams/<name>` gitlinks plus the automated `VERSION` and
  README alpha-version bump.
- no-mistakes findings are shown as resolved or open
- In `he-ship`, run `--check-review-threads` before final loop-complete once
  Copilot or human review has had a chance to run.
- Before `he-ship` loop-complete, record `ship-currentness` after final CI proof
  from `git rev-parse HEAD && git status --short`; the evidence must include
  the validated head and clean worktree status.
- If review has not run yet, record that as `ci-or-skip`/review evidence; do
  not call the repo done after known review comments exist.
- When `--check-review-threads` is used, any unresolved GitHub review thread
  keeps the evidence table open until it is resolved or explicitly handled.
- Removed local-only values include `/Users`, `/var/folders`,
  `/tmp`, `no-mistakes-evidence`, `localhost`, `127.0.0.1`, `file:`, and
  `local file`.

## Command

Run from the repository that owns the PR:

```sh
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs"
```

Useful flags:

```sh
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 3
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --screenshots /path/to/screenshots
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --e2e-video-required --videos /path/to/final-2x-video.mp4
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --e2e-video-required --videos "https://github.com/user-attachments/assets/..."
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --check-review-threads
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --dry-run
```

## Adding screenshots to a PR

Preferred path: run the repair script from the repository that owns the PR and
pass the target PR plus screenshot files or a screenshot directory.

```sh
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 3 --screenshots /path/to/screenshots
```

The script installs `gh-image` if needed, uploads images with `gh image` against
the target `owner/name` repository, stores them as GitHub `user-attachments`,
and rewrites the managed PR evidence section.

For a manual fallback, install `gh extension install drogers0/gh-image`, run
`gh image --repo owner/name <screenshot.png>`, then insert the returned Markdown
image links into the PR body with `gh pr edit <number> --body`.

Never commit screenshot files for PR evidence.
Never leave local screenshot paths in the PR body.

## Adding 2x E2E videos to a PR

For UI or phone E2E, pass the final local 2x video file or a hosted URL to the
repair script. Local 2x videos are uploaded with `gh image` and written back as
GitHub `user-attachments` links.

```sh
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 3 --e2e-video-required --videos /path/to/final-2x-video.mp4
node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 3 --e2e-video-required --videos "https://github.com/user-attachments/assets/..."
```

Do not leave local MP4/MOV/WebM paths in the PR body.
If local video upload fails, the script keeps the evidence table open and
removes all local paths from the PR body.

## If upload fails

Do not leave local file paths in the PR body.
State that screenshots or videos were captured but upload failed, include the
error at a high level, and keep the rest of the evidence section accurate.

## Verification

After updating the PR body, check:

```sh
gh pr view --json body --jq '.body' | rg -n '/Users|/var/folders|local file|no-mistakes-evidence|127\\.0\\.0\\.1|localhost|file:' || true
gh pr view --json body --jq '.body' | rg -n 'Current head|github.com/user-attachments|No-mistakes Evidence|GitHub review threads|Resolved|Open'
git status --short
```
