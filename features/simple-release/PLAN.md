# Simple release: develop merges into main

Status: Complete

## Outcome + scope

A release is one PR with head `develop` and base `main`, merged with a merge commit. A new `release source` check fails any other head, and `main` takes no direct push. The Mac canary becomes optional. Non-goals: dropping `develop`, changing the PR checks, removing `release_canary.py`.

## Repository context

Owners: `AGENTS.override.md` (release rule), `.github/workflows/release-source.yml` (new, source repository only; `update.INSTALLED_FILES` ships only `hard-eng.yml` and `pr-text.yml`), GitHub branch protection and merge settings.
Same cause: releases cherry-picked develop commits onto `main`, because only rebase merges were allowed and a GitHub rebase merge always rewrites commits. A merge commit keeps `develop` an ancestor of `main`, so the next release PR holds only new commits.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-27: keep `develop`, release with a plain merge, `main` cannot be pushed and only `develop` can merge into `main`; the Mac canary is not needed for a release.
Settings: allow merge commits; `develop` requires linear history, so its PRs stay rebase merges; `main` requires a PR, drops linear history and requires `release source`.

## Acceptance + steps

- [x] A PR to `main` from any branch but this repository's `develop` fails `release source` → N/A — GitHub runs this check only on a real PR; throwaway PR #422 from this branch showed it red, then was closed.
- [x] `main` takes no direct push → N/A — a GitHub setting, not code; the protection read-back shows a required PR with admins enforced.
- [x] A release PR runs no new-project jobs, because develop's push already checked the same tree → N/A — GitHub runs this only on a real release PR; the next release PR's `canary targets` lists none.
- [x] The new workflow passes the workflow checks → N/A — no product test; actionlint and zizmor pass.

## Baseline + execution

Result: Passed
Evidence: Branch point develop 872e48c1: `hard-eng`, `canary` and all 12 new-project jobs passed in CI.
Execution: One builder, this session.

## Risks + recovery

A merge commit on `main` is not on `develop`. Branch protection keeps `strict` off, so `develop` never has to take `main` back.

## ux_reference

N/A — CI and repository settings only; no visible UI.

## Verification

Result: Passed
Evidence: actionlint and zizmor pass locally. The live checks are recorded on the PRs.
E2E: N/A — GitHub runs the check on real PRs; no user interface.
Delivery target: Merge
Delivery: Pending — the release PR merges into `main`.
