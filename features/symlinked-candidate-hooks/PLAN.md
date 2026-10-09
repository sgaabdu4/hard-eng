# Accept a project's own hooks when the update candidate path is a symlink

Status: Complete

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
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 060868e. The new test failed on main's `.hooks` with "Git hooks point outside this repository" and passes on this branch; `tests/test_update_pr.py`, `tests/test_husky_setup.py` and `tests/test_hook_chain.py` 38 passed.
Execution: Single session on `fix/symlinked-candidate-hooks`.

## Risks + recovery

Hooks outside the repository are still rejected; only the path spelling of the checkout changes. Recovery is reverting the one line.

## ux_reference

N/A — hook path validation.

## Verification

Result: Passed
E2E: Passed — a scratch Husky project (`core.hooksPath .husky/_`) installed from main 060868e with a bare origin, on macOS's default `/var/folders` temporary directory. `python3 .hooks/hard-eng.py update` on main's `.hooks` exited 1 with "Git hooks point outside this repository: /private/var/folders/.../candidate/.husky/_ is not under /var/folders/.../candidate"; with this branch's `agent_hooks.py` it exited 0 with "No newer CI-verified Hard Eng revision is available; installed the missing pre-push hook" and left one worktree.
Evidence: `hard-eng.py check --base origin/main --plan-stage Ready` exit 0: 18 checks passed, 1453 tests, 91.07% line coverage. Codex adversarial review on GPT-6 Astra, round 1: approve, no material findings.

Delivery target: Merge
Delivery: Pending
