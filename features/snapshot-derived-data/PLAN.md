# Remove the Xcode build cache of a removed push snapshot

Status: Complete

## Outcome + scope

When a push check removes its temporary snapshot, it also removes the Xcode build cache (DerivedData) that belongs to that snapshot. Before this, every push that ran Swift or Flutter Apple tests left a cache of 0.5 to 5.5 GB that nothing could reuse, and repeated pushes filled the disk. Non-goals: caches of real checkouts, caches of other tools, and caches left by snapshots removed before this change.

## Repository context

Owners: `.hooks/ship_actions.py` `snapshot` creates and removes the push snapshot; the new `drop_derived_data` runs in its cleanup after `git worktree remove`.
Evidence: Xcode names each DerivedData folder by project path and records the path as `WorkspacePath` in its `info.plist`. Each push snapshot has a new path, so its cache was never reused or removed.
Same cause: N/A — no other Hard Eng step creates Xcode caches under a temporary path.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner gave full authority to finish the runner rollout and fix the faults found in it without asking; standing approval to push and open PRs.

## Acceptance + steps

- [x] A cache whose `WorkspacePath` is inside the removed snapshot is removed, for the raw and the resolved snapshot path → `tests/test_ship_actions.py::test_removed_snapshot_drops_only_its_xcode_build_cache` (red before).
- [x] A cache outside the snapshot, and a cache with an unreadable `info.plist`, are kept → `tests/test_ship_actions.py::test_removed_snapshot_drops_only_its_xcode_build_cache`.

## Baseline + execution

Result: Passed
Evidence: Starting tree `1c44a4c9`; the new test failed with the old `snapshot` (AssertionError on the cache inside the snapshot).
Execution: Single session.

## Risks + recovery

Only caches whose recorded project path is inside the removed snapshot are deleted, and that path no longer exists. Recovery is reverting this change.

## ux_reference

N/A — cleanup with no visible interface.

## Verification

Result: Passed
Evidence: Full pytest after the change: 2083 passed. Focused `tests/test_ship_actions.py` passes. Ruff format, ruff lint and pyrefly report no findings.
E2E: N/A — the test drives the real `snapshot` cleanup against a real Git repository and a temporary DerivedData folder.

Delivery target: Merge
Delivery: Pending — CI `hard-eng` check on the PR to `develop`, then the release to `main`.
