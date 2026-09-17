# Accept repository hooks from a linked worktree

Status: Complete

## Outcome + scope

Hard Eng runs from a linked Git worktree whose `core.hooksPath` points at the common checkout's Husky directory. `project_pre_push` accepts a hooks path inside the repository's common checkout (the parent of `git rev-parse --git-common-dir`) as well as the worktree root, maps that checkout's Husky shim to the worktree's tracked `.husky/pre-push`, and still rejects hooks outside the repository. Both callers are covered: the updater's missing-hook repair (`update.pre_push_missing` / `repair_current_hook`) and the pre-push scaffold check (`update.check_scaffold_update`, which plans setup against the worktree). No new configuration or file.

## Repository context

Owner: `.hooks/agent_hooks.py` `project_pre_push`, which accepted a hook only under the root or in `<common dir>/hooks`. In a linked worktree, `core.hooksPath` in `.git/worktrees/<name>/config.worktree` is an absolute path to the main checkout's `.husky/_`, so `git rev-parse --git-path hooks/pre-push` returns a path outside the worktree root and the check raised "Git hooks point outside this repository". Callers: `update.pre_push_missing` (used by `repair_current_hook`, so `setup.sh` could not run from a worktree) and `setup.prepare_hook` via `plan_install --plan` (used by `check_scaffold_update`, so any push containing a Hard Eng update commit was refused from a worktree). The Husky mapping returned `root / ".husky/pre-push"`, the tracked launcher, which is the file the scaffold updates; the worktree has its own copy, so the mapping keeps returning the worktree's file. Existing test: `test_committed_scaffold_exemption_preserves_application_boundary` proves a linked worktree with an external hooks path is still rejected; `tests/test_husky_setup.py` owns Husky layouts and is well under the line limit, unlike `tests/test_updates.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for this fix with tests for both paths, keeping truly external paths rejected. Commit and PR follow the user's usual go-ahead.

## Acceptance + steps

- [x] From a linked worktree whose hooks path is the main checkout's `.husky/_`, `pre_push_missing` is false, `repair_current_hook` reports no missing hook, and `check_scaffold_update` returns true → red before the fix (ValueError "Git hooks point outside this repository"), green after.
- [x] The same worktree with a hooks path outside the repository still fails both callers → same test, external branch.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at c9d526a, CI run 35249775864 success; local full check on that tree passed today with 754 tests.
Execution: Single session on `fix/worktree-hooks-path`.

## Risks + recovery

A hooks path inside the common checkout but outside `.husky/_` is accepted and returned as-is (the same treatment `<common dir>/hooks` already had), so `prepare_hook` still checks its content and refuses to overwrite a custom hook. A separate git directory (`common.name != ".git"`) keeps the old strict rule. Recovery is reverting the one function.

## ux_reference

N/A — hook path validation.

## Verification

Result: Passed
Evidence: Red with `.hooks/agent_hooks.py` stashed: `test_linked_worktree_may_use_the_common_checkout_hooks` failed at `pre_push_missing(linked)` with "Git hooks point outside this repository". Green after: the test passes, covering the updater path (`pre_push_missing` false, `repair_current_hook` reports no missing hook) and the push path (`check_scaffold_update` true from the worktree, which plans setup against it and verifies a candidate), then the external hooks path failing both callers. `tests/test_husky_setup.py` and `tests/test_updates.py` 44 passed together; ruff format and check clean; `agent_hooks.py` 377 lines.
E2E: Passed — a scratch Husky project was installed with this checkout's `setup.py`, committed, and given a linked worktree under `.claude/worktrees/task` with `extensions.worktreeConfig` and a worktree-scoped absolute `core.hooksPath` to the main checkout's `.husky/_`; `git rev-parse --git-path hooks/pre-push` there returns the main checkout's shim. With main's `agent_hooks.py` first on the path, `update.pre_push_missing` from the worktree raised "Git hooks point outside this repository"; with the fix it returned false and `setup.py <worktree> --plan` printed the hook as `.husky/pre-push` with the shell launcher. A worktree hooks path outside the repository still raises the same error.

Delivery target: PR
Delivery: Pending — full `hard-eng.py check --base origin/main` on the final tree passed: exit 0, 755 tests in 185 s, every native check passed (a first run failed only the types gate on an untyped lambda in the new test, replaced with a typed function).
