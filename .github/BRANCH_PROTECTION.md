# Branch-Protection Requirements

These are required settings for `main`. This file records the target policy. It does not claim the GitHub settings are configured.

## Pull requests

- Require a pull request for ordinary human changes.
- Require at least one approval and code-owner review.
- Dismiss stale approvals after new commits.
- Require all review conversations to be resolved.
- Require the branch to be current before merge.
- Block force pushes, branch deletion, and merge commits.
- Apply the rules to administrators.

## Required checks

- `Hard Eng (ubuntu-24.04, x64, full)`
- `Hard Eng (ubuntu-24.04-arm, arm64, setup)`
- `Hard Eng (macos-15-intel, x64, setup)`
- `Hard Eng (macos-15, arm64, full)`
- `Windows installer assets (native PowerShell)`

Skipped, cancelled, stale, or missing matrix jobs do not satisfy the policy.

## Scheduled managed-skill update

The current scheduled updater commits directly to the default branch after the full publish gate. A repository ruleset must either use a narrowly scoped updater identity for that one workflow or the workflow must be changed to open a pull request. Do not grant a general GitHub Actions or maintainer bypass. The safe target is a dedicated GitHub App that can write only the locked managed-skill paths after the named workflow succeeds.

## Administrator readback

Before claiming this policy is active, read back the repository ruleset and verify the required checks, review count, code-owner review, stale-review dismissal, conversation resolution, linear history, force-push and deletion blocks, administrator coverage, and the exact updater bypass identity.
