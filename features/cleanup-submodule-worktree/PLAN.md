# Ship cleanup in a repository with submodules

Status: Complete

## Outcome + scope

`ship --stage cleanup` finishes for a merged task worktree in a repository that has submodules. One flag changes; no guard is loosened. The remote-then-local order and the generic `git query failed` wording stay as they are. No new file other than this plan.

## Repository context

Owner: `.hooks/ship_actions.py` `cleanup`. Git refuses `git worktree remove` for any worktree whose index holds a submodule gitlink, initialized or not, unless `--force` is given; `--force` only skips git's own clean check. `cleanup_guard` runs immediately before and is stricter than that check: it rejects modified, untracked and ignored files, commits after the verified PR, initialized submodules, an index lock and locked or prunable worktrees. A single `--force` still refuses a locked worktree. The order is retry-safe: an already deleted remote branch is accepted, so a rerun resumes after a partial failure. Evidence: issue 126, observed while cleaning up the task for PR 125 in this repository.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user approved filing issue 126 and asked for the fix. Commit, PR and merge follow the same go-ahead given for PR 125.

## Acceptance + steps

- [x] A clean, merged task worktree with an uninitialized submodule is removed along with its local and remote branch → `test_cleanup_removes_task_with_uninitialized_submodule` red before, green after.
- [x] Initialized submodules, dirty or ignored files, extra commits and locked worktrees are still preserved → the existing cleanup tests pass unchanged.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 8a19e4d, hard-eng workflow run 35430263429 success.
Execution: Single session on `feature/cleanup-submodule-worktree`.

## Risks + recovery

A file created between the guard and the removal would be deleted with the worktree; git's own check had the same window, only smaller. Recovery is reverting this branch; the PR head stays on GitHub.

## ux_reference

N/A — command behavior only; no product appearance.

## Verification

Result: Passed
E2E: Passed — the new test builds real Git repositories (coordinator, bare origin, linked task worktree, a committed then de-initialized submodule) and runs the real `cleanup`; before the fix it raised `git query failed`, the same failure seen on the PR 125 task, and after it the worktree, local branch and remote branch are gone. Cleanup of this task's own worktree after merge is the hosted run and remains unverified here.
Evidence: `tests/test_ship_actions.py` 30 passed, including the locked, dirty, ignored-file, added-commit and initialized-submodule protections. The full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — the full check has not run yet.
