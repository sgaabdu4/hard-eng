# A refused update leaves a branch that can carry the fix

Status: Complete

## Outcome + scope

Two faults stopped an update in installed projects on 2026-11-13, and both are repaired.

1. A project whose gates file the new release refuses now gets its update branch. `update-pr` loads the tip of that branch with the tip's own hooks before a push. A fix commit on the update branch ships with the update. Refs [issue 615](https://github.com/sgaabdu4/hard-eng/issues/615).
2. A nested Dart package that has its own `types` check is excluded from the analysis of its parent package. The installer writes the exclusion, and the exclusion rule accepts exactly those entries. Refs [issue 616](https://github.com/sgaabdu4/hard-eng/issues/616).

Non-goals: the other build refusals that still leave no branch (a local skill edit, a local hook link); a rule that accepts one analyzer check for each folder as the owner of the `types` role; a new load rule for the gates file.

## Repository context

Owners: `.hooks/update.py::install_revision`; `.hooks/update_pr.py::publish`, `::load_refusal`, `::tip_refusal`; `.hooks/tool_setup.py::yaml_python`; `.hooks/dart_boundaries.py::nested_package_patterns`, `::exclude_nested_packages`; `.hooks/project_setup.py::validate_dart_exclusions`; `setup.py::configure_dart`, `::adopt_root_dart_gates`.
Same cause: fault 1 came with [issue 590](https://github.com/sgaabdu4/hard-eng/issues/590): its build-time load check helped against a broken update commit, and hurt, because it removed the only branch that could carry the fix. Searched `install_revision` for other build-time refusals: `validate_gates` had the same effect and moved out with it; `release_installed` keeps it. Fault 2 follows [issue 183](https://github.com/sgaabdu4/hard-eng/issues/183): the return to the root path helped on Dart 3.13, where a folder path skips analyzer plugins. Searched `setup.py` and `tests/test_setup.py` for the claim "explicit paths skip analyzer plugins": one comment and one docstring, both corrected.
Single source: the command that starts Python with `pyyaml` lives only in `tool_setup.yaml_python`; `ensure_python_runtime` and the tip load both call it. The nested package patterns come only from `dart_boundaries.nested_package_patterns`; the installer and the runner both call it. Searched `.hooks` and `setup.py` for a second `uv run --no-project --with pyyaml` list and for a second child pattern builder: none.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner gave full authority for design, merge and release on 2026-11-13, and asked that found faults are repaired in the same session.
Decision: the root analyzer check stays `dart analyze --fatal-infos .`. Measured with Dart 3.14.0: the root call reports root plugin findings inside a nested package; a root `exclude` entry for that package stops it, and the nested package's own analysis still works. One check for each folder is not accepted as the owner, because a folder path skips plugins on Dart 3.13 and misses the options and pubspec files.

## Acceptance + steps

- [x] An update whose release cannot load the gates file still leaves the update branch and an untouched checkout → `tests/test_update_pr_refusal.py::test_an_update_whose_release_cannot_load_the_gates_file_leaves_the_update_branch_and_the_checkout_untouched`
- [x] `update-pr` refuses to push a tip that its release cannot load, and names the fix steps → `tests/test_update_pr_refusal.py::test_update_pr_refuses_to_push_an_update_tip_its_release_cannot_load`
- [x] A fix on the update branch is pushed and merged → `tests/test_update_pr_refusal.py::test_a_fix_on_the_update_branch_is_pushed_and_merged_by_update_pr`
- [x] No merge is requested for an unfixed tip with only an unrelated green check → `tests/test_update_pr_refusal.py::test_update_pr_requests_no_merge_for_an_unfixed_tip_with_only_an_unrelated_green_check`
- [x] The tip load works when the host Python has no yaml → `tests/test_update_pr_refusal.py::test_the_tip_load_works_when_the_host_python_has_no_yaml`
- [x] The exclusion rule accepts only nested packages with their own `types` check → `tests/test_dart_config.py::test_dart_exclusions_accept_only_nested_packages_with_own_types_check`
- [x] The patterns follow the child `types` checks → `tests/test_dart_config.py::test_nested_package_exclusions_follow_child_types_checks`
- [x] Setup writes the exclusions, and a second run changes nothing → `tests/test_dart_config.py::test_dart_setup_excludes_nested_packages_from_root_analysis`
- [x] The runner passes the patterns to the Dart validation → `tests/test_dart_config.py::test_the_runner_passes_nested_package_patterns_to_the_dart_validation`
- [x] A new install excludes nested packages → `tests/test_setup.py::test_root_dart_install_excludes_nested_packages`
- [x] An update of a project with folder checks excludes its nested packages → `tests/test_setup.py::test_root_dart_update_excludes_nested_packages_for_a_project_with_folder_checks`
- [x] A change of only the parent package keeps the exclusion → `tests/test_dart_config.py::test_a_parent_only_change_keeps_the_nested_package_exclusion`
- [x] One setup run excludes a nested package that gets its `types` check later in the same run → `tests/test_dart_config.py::test_one_install_excludes_a_nested_package_that_gets_its_types_check_later`

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at af5c7ea4, and the Hard Eng check run of that commit passed. Each new test failed on that code for the named cause before its repair.
Execution: one builder for each fault in its own checkout, test first; one reviewer for each diff.

## Risks + recovery

- The repair of fault 1 lives in installed code. A project that still has the build-time refusal and meets a new load rule stays stuck until a setup rerun. So this release adds no new load rule.
- The tip load starts one temporary worktree for each `update-pr` run with a new release, about 0.3 seconds. Recovery: revert the commit; the build-time refusal returns.
- A project with one analyzer check for each folder keeps those checks as `project-types` after its next update and gets the root check too. The root check now passes. The project removes its folder checks in its own time.
- The exclusion follows the gates file, not the disk. A nested folder with no `types` check is never excluded.

## ux_reference

N/A — no app screen changes.

## Verification

Result: Passed
Evidence: each test of the acceptance list failed on the starting code for the named cause and passes now. The tip load ran on three real installed project trees with the plain host Python: 3 of 3 loaded. The Dart facts were measured with Dart 3.14.0 on a small fixture: the root call gave 20 findings with the nested package and 14 with the exclusion.
Review: an independent review found two faults. The first tip load ran the plain host Python, which has no yaml package, and refused each Dart project. The exclusion patterns came from the packages of one run, so a change of only the parent package refused the installer's own exclusion. Each has its own repair commit and test.
E2E: N/A — no user journey; `test_a_fix_on_the_update_branch_is_pushed_and_merged_by_update_pr` runs the real update, push and merge request against a local remote.
Retro: (1) The tip load refused each Dart project, because the test Python had yaml and the host Python has none → `tests/test_update_pr_refusal.py::test_the_tip_load_works_when_the_host_python_has_no_yaml`. (2) The first runner test gave the validation one selected package and asserted the refusal → `tests/test_dart_config.py::test_a_parent_only_change_keeps_the_nested_package_exclusion`, which goes through the real package selection. (3) The final review found that setup computed the exclusions of a parent before a later package had its `types` role → `tests/test_dart_config.py::test_one_install_excludes_a_nested_package_that_gets_its_types_check_later`. (4) The build-time load check of issue 590 had no test for the way out of its own refusal → `tests/test_update_pr_refusal.py::test_a_fix_on_the_update_branch_is_pushed_and_merged_by_update_pr`.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
