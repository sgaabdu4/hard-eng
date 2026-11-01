# Reuse the main checkout's submodule copies in temporary worktrees

Status: Complete

## Outcome + scope

A push snapshot, a new linked worktree and the update comparison tree get each submodule from a copy already on this machine, not from the network. Before this, every one of them ran `git submodule update --init --recursive --depth=1`, which downloaded every submodule again before the first check could start. Each submodule ends at its pinned commit, clean, shallow, with its original remote URL, nested submodules included. A submodule the donor does not hold at the pinned commit is fetched as before. Non-goals: CI checkout steps (`actions/checkout` clones into the main checkout, nothing local to reuse), `setup.sh` and `release_canary.py` (fresh temporary clones), and a persistent cache of submodules.

## Repository context

Owners: new `update_submodules` in `.hooks/submodules.py`; the files `update_runner.py`, `update.py` and `ship_actions.py` are each already at or near the 1000-line limit or have a different job. Callers: `prepare_checkout` in `.hooks/ship_actions.py` (serves `snapshot` and the `post-checkout` hook) with the main checkout as donor; `fetch_sources` in `.hooks/update.py` with the fresh `source` clone as donor of the `previous` tree.
Evidence: `git submodule update` always opens a connection to the remote for a missing submodule, even with `--reference`, so only a rewrite of the clone URL to the donor's git directory avoids the network. The rewrite uses `url.<donor git dir>.insteadOf=<url>`, so the stored `remote.origin.url` stays the original. A `file://` clone copies the objects into the worktree's own module directory, so nothing points back at the donor and no alternates file can outlive it.
Same cause: `update_runner.py` creates the update candidate worktree with `git worktree add` and no submodule call; the project's `post-checkout` hook runs `prepare_checkout` for it, so it is covered with no edit there. When that hook is installed, `snapshot` runs `prepare_checkout` twice; the second pass finds every submodule at its pin and does nothing.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner approved this CI and pre-push speed work on 2026-10-31, including editing, pushing, opening the PR and merging it after checks pass.
Decisions:
- A donor submodule is used only when it holds the pinned commit; otherwise that submodule fetches as today, so a stale donor cannot fail the update.
- The rewrite rules and the file-transport permission (`protocol.file.allow=always`, which Git blocks for submodules by default) apply to one `git submodule update` call that lists only the submodules with a rule. They never apply to a submodule without a matching donor.
- Recursion is done in the helper, level by level, because a nested submodule's URL and pin exist only after its parent is checked out. A final plain `git submodule update --init --recursive --depth=1` stays as the catch-all and as the fallback if the local pass fails.
- `update.py`: the fresh `source` clone has no local copy to reuse and still fetches. The `previous` tree reuses `source`'s copies only when its pin is unchanged, because `source` holds only the current pins; a moved pin is fetched as before.

## Acceptance + steps

- [x] With the remote gone, `prepare_checkout` gives a submodule and its nested submodule at their pinned commits, clean and shallow, with the original `remote.origin.url` → `tests/test_submodules.py::test_prepare_checkout_reuses_main_submodules_without_network` (red before).
- [x] Git variables inherited from a hook (`GIT_DIR`, `GIT_WORK_TREE`) do not stop the reuse → `tests/test_submodules.py::test_prepare_checkout_reuses_main_submodules_when_git_variables_are_inherited` (red before).
- [x] A donor whose submodule sits on another commit than the pin still gives the pinned commit → `tests/test_submodules.py::test_prepare_checkout_checks_out_the_pin_when_main_sits_on_another_commit`.
- [x] A donor that lacks the pinned commit does not break the update: the submodule is fetched from the remote → `tests/test_submodules.py::test_prepare_checkout_fetches_when_main_lacks_pinned_commit`.
- [x] A donor with the submodule not initialised fetches as before → `tests/test_submodules.py::test_prepare_checkout_fetches_when_main_has_no_submodule`.
- [x] `update.py` calls the helper with `source` as donor of the `previous` tree, and the helper gives an unchanged-pin tree its submodules from the donor → `tests/test_submodules.py::test_previous_revision_tree_takes_its_submodules_from_the_current_tree` (the remotes are moved away before the tree is prepared).
- [x] Time to the first `CHECK` line of a pre-push on this repository, three runs before and three after → N/A — a timing, not a behavior; the numbers are in the PR text.

## Baseline + execution

Result: Passed
Evidence: Starting tree `bb1e34f`; `test_prepare_checkout_reuses_main_submodules_without_network` failed with the old `prepare_checkout` (the submodule clone from the moved remote failed).
Execution: Single session.

## Risks + recovery

A wrong rewrite could leave a submodule at the wrong commit. The pin is read from the worktree before the update, the rewrite is only added when the donor holds that commit, and a test checks each pin. Recovery is reverting this change.

## ux_reference

N/A — no visible interface.

## Verification

Result: Passed
Evidence: Focused tests pass (`test_submodules.py`, `test_ship_actions.py`, `test_adoption.py`). Time from the start of the real pre-push entry point to its first `CHECK` line, same pushed revision and base, old root code against new, on this repository (two public submodules) with the machine busy (load 25 to 30) and a fast network: before 14.8, 7.2, 8.4 s (the first run is an outlier); after 4.5, 5.5, 5.2 s. The local gain is 2 to 3 s because a submodule download is fast here; the no-network tests are the proof, and the larger saving is on a slow network. CI `actions/checkout` is unchanged, so CI was not measured.
E2E: N/A — the tests drive the real `prepare_checkout` path and the helper `update.py` calls against real Git repositories, and the timing step runs the real pre-push entry point.

Delivery target: Merge
Delivery: Pending — CI `hard-eng` check on the PR to `develop`, then merge.
