# Make a new linked worktree work like the main checkout

Status: Complete

## Outcome + scope

`git worktree add` in an installed project gives the new worktree the main checkout's ignored `.env*` files, `.claude/settings.local.json` and `CLAUDE.local.md` (as links, never read or copied), a copy of an ignored in-tree hooks folder such as Husky's `.husky/_`, and initialized submodules. Any tool that calls `git worktree add` (agents, IDEs, people) gets this. Tracked files, skill links and committed hooks already match. Non-goals: dependency folders and caches (the lockfile gates install dependencies when `check` runs), and bare repositories.

## Repository context

Owners: `.hooks/ship_actions.py` `link_env_files` + `snapshot` already prepared the pre-push snapshot worktree (env links + submodules); this change moves that into `prepare_checkout`, reused by the snapshot and by a new git `post-checkout` hook. `.hooks/hook_chain.py` owns hook launchers, `locate` and chaining of a project's own hook (`*.project`); `agent_hooks.project_pre_push` maps Husky shims and now does so for any hook name. `setup.py` `install` writes and commits hooks; `update.repair_current_hook` / `repair_installation` restore a missing hook at session start, so existing installs get the new hook without a new release step.
Evidence: in a Husky project, `git rev-parse --git-path hooks/pre-push` in a fresh worktree names `.husky/_/pre-push`, which does not exist there, so pushes from that worktree ran no Hard Eng checks. A fresh worktree also had no `.env` files.
Same cause: N/A — new setup behavior, not a fault fix.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked that every scaffolded project's worktrees work like the main checkout and get env files automatically; standing approval to push and open PRs. Decided: link env and local settings (one source, secrets never read or duplicated); copy only the hooks folder, because Git does not apply the ignore file inside a linked folder; a failed preparation prints a warning and does not fail `git worktree add`.

## Acceptance + steps

- [x] A fresh worktree links each ignored local file to the main checkout's file, leaves build output out, keeps skill links and a clean status, and has a working Hard Eng pre-push hook, for plain Git hooks and Husky → `tests/test_hook_chain.py::test_a_new_worktree_matches_the_main_checkout` (red before: no `.env` link).
- [x] Creating a worktree of another branch never runs that branch's code; the main checkout's copy prepares it → `tests/test_hook_chain.py::test_a_new_worktree_matches_the_main_checkout` (`review` worktree, red before).
- [x] A project's own `post-checkout` hook is kept and still runs → `tests/test_hook_chain.py::test_a_new_worktree_matches_the_main_checkout` (`project.args`).
- [x] An existing install without the worktree hook gets it at the next session repair → `tests/test_hook_chain.py::test_a_new_worktree_matches_the_main_checkout` (`repair_current_hook`).
- [x] The pre-push snapshot still links env files and initializes submodules → `tests/test_ship_actions.py::test_pre_push_snapshot_has_its_own_git_environment`.

## Baseline + execution

Result: Passed
Evidence: Starting tree `fbbb031`, full pytest: 1725 passed, 9 failed. All 9 need tools or process handling this container lacks (`dart`, `xccov`, child-process reaping). `check` could not provision gitleaks, osv-scanner, shellcheck, actionlint, biome and jscpd, because the session network policy blocks GitHub release downloads; CI runs those gates.
Execution: Single session.

## Risks + recovery

`post-checkout` also runs for Hard Eng's own snapshot and update worktrees; preparation is idempotent and the snapshot calls the same function. The launcher returns early unless the previous HEAD is all zeros, so normal `git switch` costs one shell `case`. Recovery is deleting the `post-checkout` launcher or reverting this change.

## ux_reference

N/A — git hook behavior with no visible interface.

## Verification

Result: Passed
Evidence: The new test failed before the change (no `.env` link) and passes for both hook layouts. Full pytest after the change: 1727 passed, the same 9 environment failures as the baseline and no new ones. Ruff format, lint, complexity, annotations, pyrefly and vulture pass. Changed files stay under 1000 lines.
E2E: Passed — real `git worktree add` on an installed project with plain Git hooks and with Husky → `test_a_new_worktree_matches_the_main_checkout`.

Delivery target: PR
Delivery: Pending — CI `hard-eng` check on PR #326.
