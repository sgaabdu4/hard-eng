# Accept a project's own hooks when the update candidate path is a symlink

Status: Ready

## Outcome + scope

Issue 257. On macOS the background update's candidate worktree lives under `/var/folders`, a symlink to `/private/var/folders`. A project with a relative `core.hooksPath` such as Husky's `.husky/_` failed every background update with "Git hooks point outside this repository", because `project_pre_push` compared the resolved hook folder with the unresolved checkout path. The comparison now resolves both sides. No new file other than this plan.

## Repository context

Owner: `.hooks/agent_hooks.py` `project_pre_push`. Reached from `update_runner.build_update` → `update.update(candidate)` → `repair_current_hook` → `pre_push_missing` when no newer release exists. `setup.py` resolves its repository argument, so the published setup route was not affected.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix it, file and close the issue, and run a GPT-6 Astra Codex adversarial review loop before the PR, acting only on genuine, realistic, substantial findings.

## Acceptance + steps

- [x] A Husky project's background update succeeds when the temporary directory is reached through a symlink → `test_husky_update_succeeds_when_the_temporary_directory_is_a_symlink` (fails on main with the issue's error).
- [ ] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 060868e. The new test failed on main's `.hooks` with "Git hooks point outside this repository" and passes on this branch; `tests/test_update_pr.py`, `tests/test_husky_setup.py` and `tests/test_hook_chain.py` 38 passed.
Execution: Single session on `fix/symlinked-candidate-hooks`.

## Risks + recovery

Hooks outside the repository are still rejected; only the path spelling of the checkout changes. Recovery is reverting the one line.

## ux_reference

N/A — hook path validation.

## Verification

Result: Pending
Evidence: Pending

Delivery target: Merge
Delivery: Pending
