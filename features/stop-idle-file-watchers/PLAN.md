# Stop Git file watchers of worktrees unused for a day

Status: Complete

## Outcome + scope

Each background update stops the Git file watcher (`fsmonitor--daemon`) of any other worktree of the repository whose index has not changed for 24 hours. Git starts a watcher again on the next command in that worktree, so a forgotten worktree no longer keeps one running indefinitely.

Non-goals:
- Removing forgotten worktrees: their commits and edits belong to their tasks; `ship --stage cleanup` and Claude's worktree cleanup own that.
- Repositories without Hard Eng, or ones where no session starts: the update runs only at session start in an installed repository.
- The checkout the session starts in: it is in use.

## Repository context

Owners:
- `.hooks/update_runner.py` `remove_stale_candidates`: runs in the detached update process at every session start, lists the repository's worktrees and removes Hard Eng's leftover ones.
- Git 2.55 `fsmonitor--daemon` has no idle timeout; a watcher runs until it is stopped, its worktree is deleted or the machine restarts. Repositories with `core.fsmonitor true` in `.git/config` start one in every worktree on its first Git command. On this Mac, 13 watchers were running (193 MB) for project checkouts and task worktrees 2–18 hours old.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to add this to Hard Eng in a new PR after asking what happens when a worktree is forgotten.

## Acceptance + steps

- [x] Update cleanup stops the watcher of a worktree whose index is a day old, and keeps the watcher of a recently used worktree and of the checkout the update runs in → `test_update_cleanup_stops_file_watchers_of_worktrees_idle_for_a_day`.

## Baseline + execution

Result: Passed
Evidence: main `5c286c5a` passed the Hard Eng workflow on push (run 36657723970).
Execution: One builder on branch `stop-idle-fsmonitor`.

## Risks + recovery

Each update runs one `git rev-parse` per worktree, in the detached update process, so session start does not wait on it. A stopped watcher costs one full scan on the next Git command in that worktree. Recovery is reverting the change.

## ux_reference

N/A — background cleanup; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (1163 tests, 89.93% line coverage). The acceptance test failed without the change (the idle worktree's watcher kept running) and passed with it, using real Git 2.55 watchers.
E2E: N/A — the test runs real watchers in real Git worktrees; installed repositories take the change with their next update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
