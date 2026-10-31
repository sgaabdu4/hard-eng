# Replace a merged update branch with the next release

Status: Complete

## Outcome + scope

`update-pr` builds the next verified release when the local `hard-eng/update` branch is left over from an update that already merged, even when that branch records the same revision as the base. Before this, the leftover branch made `update-pr` print "Nothing to publish" while a newer release waited. A branch whose commits already landed through a rebase or squash merge counts as merged. Non-goals: branches with fixes beyond the update commit, uncommitted edits in the branch worktree, and the remote branch.

## Repository context

Owners: `.hooks/update_pr.py` `publish` decides whether to rebuild the branch; `unfinished_update` and `landed` already tell a merged branch from someone's work. The new `merged_update` reuses the same `rev-list --cherry-pick` count and `landed` test.
Evidence: after a rebase merge of an update, the local branch kept the merged revision. `revision == current` then skipped the rebuild, so the next release was never built.
Same cause: N/A — the earlier rebuild rule covered only a branch whose revision differs from the base.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner gave full authority to finish the update rollout and fix the faults found in it without asking; standing approval to push and open PRs.

## Acceptance + steps

- [x] A leftover update branch that landed through a rebase merge is replaced by the next release, which is pushed → `tests/test_update_pr.py::test_update_pr_alone_replaces_a_merged_update_branch_with_the_next_release` (`rebase_merge_update`, red before).
- [x] The same holds after a squash merge → `tests/test_update_pr.py::test_update_pr_alone_replaces_a_merged_update_branch_with_the_next_release` (`squash_merge`, red before).
- [x] Without a newer release, a merged branch still publishes nothing → `tests/test_update_pr.py::test_update_pr_publishes_nothing_after_a_merged_fix_without_a_newer_release`.
- [x] A fix pushed to the update branch is never overwritten → `tests/test_update_pr.py::test_update_pr_does_not_overwrite_a_fix_pushed_to_the_remote_branch`.

## Baseline + execution

Result: Passed
Evidence: Starting tree `d546ab44`; the new test failed in both merge forms with the old `publish` (`tests/test_update_pr.py:373` AssertionError).
Execution: Single session.

## Risks + recovery

A branch that holds only commits already on the base is rebuilt. Such a branch has no unique work, so nothing is lost. Recovery is reverting this change.

## ux_reference

N/A — command behavior with no visible interface.

## Verification

Result: Passed
Evidence: Full pytest after the change: 2082 passed. Focused `tests/test_update_pr.py`, `tests/test_update_runner.py` and `tests/test_updates.py` pass. Ruff format passes.
E2E: N/A — the test drives the real `update-pr` against real Git repositories and a local remote.

Delivery target: Merge
Delivery: Pending — CI `hard-eng` check on the PR to `develop`, then the release to `main`.
