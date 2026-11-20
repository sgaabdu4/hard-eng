# Cut the setup around the CI-mode push scan and name a stopped push check

Status: Complete

## Outcome + scope

With `pre_push_checks: "ci"`, the pre-push hook sets up no copy files for the commit secret scan, and a push check that a signal stops says so, so the update PR no longer calls that a project fault. Non-goals: the full local mode, the mutation path, any check or limit.

## Sources + coverage

Sources: N/A — the request is a maintainer fault report from an installed project; no outside source.

## Repository context

Owners: `.hooks/ship_actions.py` (`pre_push`, `snapshot`, `prepare_checkout`, `run_hard_eng`), `.hooks/update_pr.py` (`publish`), `.hooks/process_group.py` (`exit_when_stopped`, `STOP_SIGNAL`).
Same cause: N/A — no earlier fix of this cause. The copy for a pre-push check is made in `snapshot`, and `mutate` uses it with the default full setup; only `pre_push` knows whether the checks read the setup.
Single source: N/A — the stop wording has one owner, `stopped_line` in `ship_actions.py`; the push-failure text has one owner in `update_pr.publish`. No other copy found by searching `.hooks` and `tests` for "stopped by" and "failed; the lines above".

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer approved this fault report on 2026-11-20 and wants CI-only gates with no slow local checks. Merge: maintainer, standing instruction to push, watch CI and rebase-merge Hard Eng task PRs when green ("keep going and merge when green", since 2026-10-07); this PR merges into develop by rebase.

## Acceptance + steps

- [x] In CI mode with no mutation run, the copy of the pushed commit gets no submodule clone, no local file links and no post-checkout hook → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_sets_up_no_copy_for_the_secret_scan`
- [x] In CI mode with a mutation budget, the copy gets the full setup, because the quick check and mutation read installed dependencies → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_sets_up_the_copy_when_mutation_will_run`
- [x] Local mode keeps its setup → `tests/test_push_check.py::test_a_push_that_runs_the_full_check_still_sets_up_the_copy`
- [x] The scan still refuses a pushed commit with a secret that a later commit removed (guard; already held before the change) → `tests/test_push_check.py::test_the_commit_secret_scan_blocks_a_leaked_secret_when_checks_are_left_to_ci`
- [x] A changed or added working-tree `.gitleaks.toml` or `.gitleaksignore` does not hide a pushed secret (guard; already held before the change) → `tests/test_push_check.py::test_a_changed_working_tree_gitleaks_config_does_not_hide_a_pushed_secret`
- [x] CI mode keeps the full setup when a package of the pushed gates file sits in a submodule or leaves its folder with `..` → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_sets_up_the_copy_for_a_package_in_a_submodule`
- [x] A pre-push hook that SIGTERM or SIGHUP stops prints one line naming the signal and saying the stop is not a fault in the project → `tests/test_pre_push_stop.py::test_a_pre_push_stopped_by_a_signal_says_the_check_did_not_finish`
- [x] A check that exits with 128 plus the signal gets the same line; a check that fails on its own gets none → `tests/test_pre_push_stop.py::test_a_check_that_the_signal_reached_first_gets_the_same_line`, `tests/test_pre_push_stop.py::test_a_check_that_fails_on_its_own_gets_no_stop_line`, `tests/test_pre_push_stop.py::test_a_check_that_a_signal_ended_before_its_handlers_start_gets_the_same_line`, `tests/test_pre_push_stop.py::test_an_interrupted_mutation_report_does_not_ask_for_another_push`
- [x] The update PR names both cases when its push fails: a printed failing check is a project fault, and no printed failing check (for example a stopped check) is not → `tests/test_update_pr_refusal.py::test_a_refused_push_of_the_update_branch_names_the_next_step`

## Baseline + execution

Result: Passed
Evidence: 2026-11-20, a large installed project (12.9k tracked files, no skill submodules, scan-only push of one commit), cloned to a scratch folder with a local bare repository as the push target. Each step timed by wrapping the functions in a scratch script, not in tracked code. Old ci-mode pre-push, total seconds: cold tool install 28.2; warm 11.1, 9.9, 8.7, 8.8. Steps of a warm run: remote base lookup 1.0 to 2.0 (done twice, 0.7 to 1.8 more), `git worktree add` 2.2 to 2.5, local file links 0.07 to 0.10, submodule update 0.00, the child check 2.4 to 4.3 (secret scan itself 0.24 to 0.37), `git worktree remove` 0.8 to 1.0. With two small skill submodules in the push: `git worktree add` 2.8 to 3.0, the second prepare 0.4. With the submodules missing from the main checkout: `git worktree add` 4.7 to 5.1, because the post-checkout hook clones them, then the second prepare 0.4 more. `git worktree add` fires the post-checkout hook (submodule folders were filled with the hook and empty with `core.hooksPath=/dev/null`; the hook costs about 1.0 s with a donor and 3 s with a clone), so the copy was prepared twice. The reported 51 to 134 s did not reproduce: the largest measured parts were the first tool install (17 s of 28 s) and the network clone of submodules.
Execution: One builder, this session. Not checked: a push from a linked worktree, a slow network clone of large submodules, and the `imported_files` scan of ignored Dart files.

## Risks + recovery

A project whose scan reads an ignored local file would lose it in CI mode. The scan reads only the tracked files of the pushed commits and its pushed config, and the plan checks read tracked files; the guard tests above hold that. Recovery: revert the `scan_only` argument in `pre_push`.

## ux_reference

N/A — no visible UI.

## Verification

Result: Passed
Evidence: Same large project and method as the baseline, develop hooks with and without this change, two runs each, total seconds of the ci-mode pre-push: old 12.65 and 11.24, new 7.37 and 7.14. In the old runs `git worktree add` with its hook took 5.1 and 5.9 s and the second prepare 0.4 s; the new runs start no hook and no prepare, so the total falls by about 4 to 5 s. The remote base lookup, the child check and the worktree remove are unchanged. Tests: tests/test_push_check.py, tests/test_pre_push_stop.py, tests/test_update_pr_refusal.py and tests/test_ship_actions.py pass (128 tests). The three failures of tests/test_snapshot_imports.py on this machine also fail on the unchanged develop.
E2E: N/A — no user journey changes; the hook tests run the real hook with a real signal.
Real service: N/A — no outside service
Retro: (1) The ci-mode push built a full copy for a scan that reads only tracked files → fixed at the cause in `pre_push`, with a test for each of the three modes. (2) The first scratch timings missed the cost because the copy was warm and held no submodules → the plan lists the runs with and without submodules and names what was not checked. (3) A push stopped by a signal looked like a project fault → the hook now names the signal, and the update PR names both cases.
Who sent the stop in the reported run: not checked. The log shows only the exit code 143 after the tool setup; a time limit in the caller is possible, because the reported times straddle 120 s. Hard Eng's own limits end a command with SIGKILL after a timeout, not SIGTERM.

Review declined: the plan quotes a standing push and merge instruction, which could steer a read-only reviewer :: the Authority line is required text from the maintainer, and the reviewer is read-only by its own assignment.

Review declined: a package path that reaches a submodule through a tracked symlink still gets an empty submodule in CI mode :: a gates file naming a package through a symlink into a skill submodule is far-fetched, and the full setup still runs for every path with `..` or inside a submodule.

Review declined: the retry text names `update-pr` without `--no-merge` :: the text named the same command before this change, and the retry only merges when checks pass, which the plain command is meant to do.
Review declined: a signal that arrives after the scanner exited with a finding, while the runner reads its report, labels that gate as stopped :: the window is a few milliseconds, and the next push prints the finding plainly.
Review declined: a stop that lands before a scanner prints its startup text leaves a FAIL line without the stop note :: this is the gate runner's own message path in the full local check, outside the CI-mode push this plan changes; the stop line still names the signal, and the next run shows the real result.

Delivery target: Merge

Delivery: Pending — required remote proof.
