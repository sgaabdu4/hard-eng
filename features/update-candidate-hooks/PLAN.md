# Run the update candidate's own hooks and name the project as the cause of a rejected commit

Status: Complete

## Outcome + scope

Issue 247. The background update builds its commit in a fresh `git worktree add` candidate. With `extensions.worktreeConfig` on, Git copies the calling worktree's `config.worktree` into the candidate, including an absolute `core.hooksPath` into the main checkout, so the candidate ran the main checkout's hooks instead of its own. The candidate now rewrites an inherited absolute worktree-scoped hooks path that lies inside the calling worktree or the main checkout as the same path relative to the candidate, so the candidate runs its own copy of those hooks. A relative path already resolves inside the candidate, and a hooks folder outside the repository is the same for every checkout; both are kept. When the update commit is still rejected, the error now says the project's commit hook failed in a fresh checkout with no package install, and that the fix belongs in the project's hook (quick guards in pre-commit, verification in pre-push), not in Hard Eng. The optional setup warning from the issue is not added. No new file other than this plan.

## Repository context

Owner: `.hooks/update_runner.py` `build_update` (candidate creation) and `git_commit` (the rejected-commit error). The rewrite lives in `.hooks/hook_chain.py` `use_own_hooks`, the module that owns the project's Git hooks, because `update_runner.py` is at the 1000-line limit. `git worktree add` on Git 2.55 copies `config.worktree` into the new worktree; a fresh candidate has no setting of its own, so everything in its `config.worktree` is inherited, and an absolute hooks path there names another checkout's hooks. The main checkout is the parent of the common `.git` directory, as `agent_hooks.project_pre_push` already assumes. The candidate's file is edited with `git config --file <candidate config.worktree>`, never `--worktree`, because without the extension `--worktree` would edit the shared `.git/config`. `update.update`, the only production caller of `git_commit`, runs only inside that candidate, so the message's "fresh checkout" wording holds.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open issues; 247 was the only one open, and to run an adversarial Codex review loop before the PR.

## Acceptance + steps

- [x] An update started from a linked worktree whose `config.worktree` points `core.hooksPath` at a rejecting hook still prepares the update branch, and the linked worktree keeps its setting → `test_update_from_a_linked_worktree_ignores_its_inherited_hooks_path`; failed with the fix disabled, passes with it.
- [x] A relative hooks path stays, an absolute one inside the checkout becomes relative, and one outside the repository stays → `test_update_candidate_runs_its_own_copy_of_the_inherited_hooks_path` (added after the first two Codex reviews).
- [x] A rejected update commit names the project's hook as the cause → `test_failed_update_restores_the_skill_folder_link` extended.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at d370168.
Execution: Single session on `feature/update-candidate-hooks`.

## Risks + recovery

A Husky project whose `.husky/_` is untracked runs no pre-commit hook in the candidate, the same as a fresh clone; the update PR's checks remain the gate. Recovery is reverting this branch.

## ux_reference

N/A — command-line error text only; no product appearance.

## Verification

Result: Passed
E2E: Passed — outside pytest, a scratch Python project installed at 6a4e86f with a local bare origin and a linked worktree whose `config.worktree` set `core.hooksPath` to a rejecting hook folder inside the main checkout. `hard-eng.py update` from the linked worktree with the installed updater recorded `git commit exited 1: stale hook from the main checkout`. With this branch's `update_runner.py` and `hook_chain.py` the same run prepared `hard-eng/update` at d370168 and the linked worktree still held its own hooks path. With the linked worktree pointing at a tracked rejecting `.githooks` folder in the main checkout and no shared setting, the update was rejected by the candidate's committed hook, not by an edited copy in the main checkout. With a rejecting shared `.git/hooks/pre-commit`, the recorded result carried the hook's text and the new project-hook guidance. (With a hooks folder outside the repository, the old updater also failed earlier with "Git hooks point outside this repository"; the fix removes that path too.)
Evidence: the focused tests pass; the linked-worktree update test failed with `hook_chain.use_own_hooks` replaced by a no-op (first version).

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all checks passed, 1441 tests and 4 performance checks. A first run failed the 1000-line limit on `update_runner.py`; the new step moved to `hook_chain.py` before the passing run. Commit, PR CI, merge, merged-main CI and cleanup remain unverified.
