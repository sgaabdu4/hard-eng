# Repair the three open issues of the hooks folder and the update load check

Status: Complete

## Outcome + scope

Three open issues are repaired, one commit for each fault.

1. Issue 610: a first install commits its files when the hooks folder is inside the work tree and Git ignores it. The ignored hook and its kept copy stay local files.
2. Issue 611: an update commit chains a tracked project `post-checkout` hook. It replaces the hook with the worktree launcher and adds the kept copy, as a first install does.
3. Issue 612: the load check of an update also loads the debt file with the code of the new release.
4. The Plain STE output style no longer gives a sentence count for a short reply. The owner approved this edit after a prompt audit on 2026-11-14.

Non-goals: a load of `trello.json` at update time; a full load in a setup rerun; a change of the refusal for a kept copy that differs from its hook.

## Repository context

Owners: `.hooks/hook_chain.py::committed_hook_names`, `::chain_worktree_hook`, `::plan_env`, `::keep_copy_mode`; `setup.py::install` and its `--plan` output; `.hooks/update.py::update_plan`, `::install_revision`; `.hooks/update_runner.py::commit_update`; `.hooks/update_pr.py::LOAD_CHECK`.
Same cause: 610 → `update.local_state` asks Git for ignored paths and has three callers. `setup.py::install` had the fault. `update.py` passes only file and link changes, so no hook path reaches it. `update_runner.refuse_untracked_overlap` must refuse real overlaps. `stale_updates.worktree_place` already handles an ignored hook for updates (helped). 611 → the only code that chains a worktree hook is `setup.py::install` and the repairs of `install_worktree_hook`; none of them builds an update commit, and the repair of issue 589 (helped) left this path open on purpose. 612 → issue 590 added `load_groups` to the load check (helped); the debt loader is the only other loader that each check runs.
Single source: the rule for which hook paths an install commits lives only in `hook_chain.committed_hook_names`; `setup.py::install` held it before and now calls it. The chain files of an update come only from `hook_chain.chain_worktree_hook`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner asked on 2026-11-13 for no open issue, and gave full authority for design, merge and release.
Decisions:

1. The update does not load `trello.json`. No check in `.hooks` loads that file, so a load at update time is a new blocking rule and not a repair.
2. A setup rerun keeps its parse-only write of the gates file. The next check loads the file and names the fault, and the rerun has no branch on which to hold a refused file.
3. The chain files go into the `files` of the setup plan, because the installed updater of the old release builds the commit and reads only that list. Each plan that is not an update commit sets `HARD_ENG_LOOSE_PLAN`, and setup then leaves the chain out. A switch in the environment is safe with an older `setup.py`, which a new option is not.
4. An old updater writes a new file with no run permission, and the launcher of a Git hooks folder skips a copy that it cannot run. So that folder gets its chain only when the installed release keeps the mode of a copy. Such a project gets its chain one update later. A Husky hook has no such limit.
5. An untracked kept copy that differs from the tracked hook stops the update with the present refusal for untracked files. The owner decides which text is the hook.

## Acceptance + steps

- [x] A first install commits its files when the hooks folder is ignored → `tests/test_install_ignored_hooks.py::test_a_first_install_commits_its_files_when_the_hooks_folder_is_ignored`
- [x] The worktree hook and the kept copies of an ignored hooks folder stay local files → `tests/test_install_ignored_hooks.py::test_the_worktree_hook_and_kept_copies_of_an_ignored_hooks_folder_stay_local`
- [x] A hooks folder that is not ignored still commits its hook → `tests/test_install_ignored_hooks.py::test_a_hooks_folder_that_is_not_ignored_still_commits_its_hook`
- [x] A tracked hook takes its kept copy into the commit when only the copy is ignored → `tests/test_install_ignored_hooks.py::test_a_tracked_hook_takes_its_kept_copy_into_the_commit_when_only_the_copy_is_ignored`
- [x] An ignored installed path with local content still blocks the commit → `tests/test_install_ignored_hooks.py::test_an_ignored_installed_path_with_local_content_still_blocks_the_commit`
- [x] A new worktree runs the owner hook and the preparation from an ignored hooks folder → `tests/test_install_ignored_hooks.py::test_a_new_worktree_runs_the_owner_hook_and_the_preparation_from_an_ignored_hooks_folder`
- [x] The update commit holds the launcher and the kept copy with its mode, a new worktree runs both, and a second update changes nothing → `tests/test_update_hooks_folder.py::test_the_update_commit_chains_a_tracked_project_post_checkout_hook`
- [x] A project with no own hook gets no hook in the update commit → `tests/test_update_hooks_folder.py::test_a_project_without_its_own_post_checkout_hook_gets_no_hook_in_the_update_commit`
- [x] A tracked hook that is the launcher stays out of the update commit → `tests/test_update_hooks_folder.py::test_a_tracked_hook_that_is_already_the_launcher_stays_out_of_the_update_commit`
- [x] A kept copy that matches the hook gets only the launcher → `tests/test_update_hooks_folder.py::test_a_kept_copy_that_matches_the_tracked_hook_gets_only_the_launcher`
- [x] A kept copy that differs from the hook refuses the update → `tests/test_update_hooks_folder.py::test_a_kept_copy_that_differs_from_the_tracked_hook_refuses_the_update`
- [x] An old updater chains only a hook that needs no mode → `tests/test_update_hooks_folder.py::test_an_installed_updater_that_gives_a_new_copy_no_mode_chains_only_a_hook_that_needs_none`
- [x] An untracked kept copy of the owner stops the update → `tests/test_update_hooks_folder.py::test_an_untracked_kept_copy_of_the_owner_stops_the_update_that_would_replace_it`
- [x] An untracked project hook is not chained for a commit → `tests/test_hook_chain.py::test_an_untracked_project_post_checkout_hook_is_not_chained_for_a_commit`
- [x] The plan rule starts no more processes than before, also beside an update → `tests/test_change_size.py::test_the_plan_rule_starts_no_more_processes_than_before_for_an_installed_path`
- [x] The output style gives no sentence count for a short reply → N/A — no test can judge the length of a reply; the install test still reads the style file
- [x] The load check refuses a debt file that each check refuses, and accepts a good one → `tests/test_update_pr_refusal.py::test_the_tip_load_refuses_a_debt_file_that_each_check_would_refuse`

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 43bfc7d1, and the Hard Eng check run of that commit passed.
Execution: one builder for issues 610 and 611, test first; the coordinator for issue 612 and the integration.

## Risks + recovery

- A project with a tracked hook in a Git hooks folder gets its chain one update later than a Husky project (Decision 4).
- An update commit that holds hook paths takes the full checks, not the short checks of a scaffold-only update.
- The new chain function skips a hook that is a link, that is not UTF-8 text or that is outside the work tree. Such a project keeps its present state.
- Recovery: revert the three commits; no data step.

## ux_reference

N/A — no screen changes; the texts that setup and the update print are the same.

## Verification

Result: Passed
Evidence: each new test failed before its code for the named cause and passes now. For 610 the install printed "not committed (these paths already had local changes: .githooks/pre-push)". For 611 the hook path and the kept copy were absent from the update commit. For 612 the load check gave no refusal. The static gates and the focused tests passed on the combined branch. The new chain function ran read-only on 38 real installed projects: no refusal, and no project has this hook state.
Review: the independent challenge ran on the final commit.
E2E: N/A — no user journey changes; the tests run a real install, a real update and a real `git worktree add`.
Retro: (1) Issue 610 came from the base branch → the gate is the install test; `test_install_commits_only_clean_installed_paths` had no ignored hook path, and `tests/test_install_ignored_hooks.py::test_a_first_install_commits_its_files_when_the_hooks_folder_is_ignored` now fails on that revision. (2) Issue 611 came from the base branch → the gate is the update test; the tests of issue 589 ran only the repair path with no newer release, and `tests/test_update_hooks_folder.py::test_the_update_commit_chains_a_tracked_project_post_checkout_hook` now runs a real newer release. (3) Issue 612 has no failing release → `tests/test_update_pr_refusal.py::test_the_tip_load_refuses_a_debt_file_that_each_check_would_refuse`. (4) The first form of the chain made an owner hook stop without a message under an old updater → `tests/test_update_hooks_folder.py::test_an_installed_updater_that_gives_a_new_copy_no_mode_chains_only_a_hook_that_needs_none`. (5) The review found that a tracked hook lost its kept copy from the commit when only the copy was ignored → `tests/test_install_ignored_hooks.py::test_a_tracked_hook_takes_its_kept_copy_into_the_commit_when_only_the_copy_is_ignored`. (6) The push check failed: the first form of the chain added 3 process starts to the plan rule → Ran too late: the builder brief did not list `tests/test_change_size.py` as a focused test for a change of `update_plan`; the coordinator now runs it before the push.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
