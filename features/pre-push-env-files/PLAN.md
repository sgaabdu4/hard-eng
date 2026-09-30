# Give the pre-push snapshot the project's ignored .env files

Status: Complete

## Outcome + scope

Pre-push and mutation snapshots link the repository's gitignored `.env*` files into the temporary checkout, so builds that read local settings (for example Next.js pages fetched at build time) pass pre-push as they do in the checkout. The links point at the originals; Hard Eng never reads, copies or prints their contents. Committed code stays the only code under test: uncommitted edits to tracked files are still excluded.

Non-goals: other ignored files (dependencies, caches), and CI, which supplies settings through its own environment.

## Repository context

Owners: `.hooks/ship_actions.py` `snapshot`: adds a detached worktree at the pushed revision, which holds only tracked files, so a build needing `.env` failed there although the same check passed in the checkout. Reproduced by an installed Next.js site whose build fetches Appwrite data: `check --base origin/main` passed 18/18 in the checkout, and pre-push failed `build` with "Endpoint must be a valid string".

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user chose to fix Hard Eng and take the update in the affected site's CI PR.

## Acceptance + steps

- [x] Ignored `.env` at the root and `.env.local` in a package appear in the snapshot as links to the originals → `test_pre_push_snapshot_has_its_own_git_environment`.
- [x] An uncommitted edit to a tracked file stays out of the snapshot → the same test.
- [x] The originals are unchanged after the snapshot is removed → the same test.

## Baseline + execution

Result: Passed
Evidence: the test fails against main `5c286c5a`.
Execution: One builder on branch `fix/pre-push-env-files`.

## Risks + recovery

A project whose tests must not see local settings now sees them in pre-push, as it already does in `check`. `git ls-files --directory` keeps discovery cheap by collapsing ignored directories. Recovery is reverting the commit.

## ux_reference

N/A — pre-push behaviour; no product appearance.

## Verification

Result: Passed
Evidence: GATE_EVIDENCE
E2E: N/A — the test runs the real pre-push path on a Git fixture; the affected site's push proves it end to end once it takes this update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
