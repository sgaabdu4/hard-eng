# Split the CI tests over shard jobs, and fix three canary faults

Status: Ready

## Outcome + scope

A project can split its pytest tests gate over CI shard jobs with `"shards": N`, and this repository runs its tests in six shards. Shards are opt-in for each project. A project without the field keeps the one-job workflow. The required check keeps its name, `hard-eng`. Three canary faults are fixed: one total time limit for the GitHub lookups of a push, a false summary line on a release PR, and a pass line that names no unit. An audit of the released code runs now. Each fault that it reproduces in normal use joins this plan as a new slice.

Non-goals:

- Trusted code for the CI jobs: a later plan.
- The cheaper file walk: a later plan.
- The rule for an edited old finished plan that passes today's rules: a later plan.
- Shards for a tests gate that does not run pytest directly. Setup refuses it.
- Fewer runners on a reused push. Each job still starts and prints the reuse line.

## Repository context

Owners: `.hooks/shards.py` (new) owns the shard split, the shard runs, the report merge, the proof marker and the shard form of the workflow. `.hooks/gate_config.py` owns the check of the `shards` field. `.hooks/ci_jobs.py` owns the `--shard` flag. `.hooks/hard-eng.py` owns `check` and the calls into the shard module. `.hooks/dart_boundaries.py` gets the two Dart settings checks from `.hooks/gate_config.py`. `.hooks/ci_setup.py` owns the template path and the workflow migrations. `.github/hard-eng.yml` (new) is the template that setup installs. `.github/workflows/hard-eng.yml` becomes the generated shard form of this repository. `hard-eng.gates.json` owns the gates of this repository and the format gate of the shipped files. `release_canary.py` and `.github/workflows/canary.yml` own the new-project jobs, the canary trigger and the release gate.
Same cause: five causes. (1) One test job sets the CI time of a project. Earlier fix: the reuse rule of round ten skips checks that passed on the same files; it helped only for repeated runs. Other places: none; the Swift split moves only Swift gates to macOS. (2) A job that runs with no tools makes a decision that needs a tool. The gate job runs bare `python3`, and the scaffold-only proof of an update PR starts `uv` through `update_plan`. With no `uv` on the path, the gate fails while the shard jobs proved the tree. Earlier fix: none. Other places, searched: the `impact` step runs the same proof with bare `python3`, but it catches the error and the full check follows. Fixed here: the gate job runs no proof and takes the proof of a shard job. (3) The time limit of a call equals or passes the limit of its job, so GitHub ends the job before the fallback. Earlier fix: the lookups of a push got one total limit of 120 seconds (this plan). Other places, searched in `release_canary.py` and each workflow: the release gate waits up to 3,600 seconds, then makes more lookups of up to 300 seconds each, and the `canary` job limit is 65 minutes (3,900 seconds); fixed here. The new-project steps have a limit of 3,600 seconds in a 60-minute job, and a gate of `check` in CI has a limit of `ci_seconds` (600) in a 10-minute job. Not changed: in both, the job fails either way, and no fallback runs after the limit; only the stop text is lost. The `pr text` and `release source` jobs set no time limit on a call. (4) A summary line claims a result that a later step decides. Earlier fix: none. Other places, searched in `canary.yml` and `release_pr_gate`: the release gate prints the same words only when the diff holds no installed file, which is true there. (5) A pass line hides what ran. Earlier fix: the `project lint` unit of round ten. Other places: the agent units already print their own name.
Single source: the `shards` field has one check, `validate_shards` in `.hooks/gate_config.py`. The shard job texts, the artifact pins, the marker name and the shard note have one owner, `.hooks/shards.py`. The template path has one owner, `TEMPLATE` in `.hooks/ci_setup.py`, with `TEMPLATE_BEFORE_MOVE` for a release tree from before the move; each migration reads it through `template_text`. The two quoted workflow lines have one owner, the template; the migration names the same two lines. The lookup limit has one owner, `PUSH_LOOKUP_SECONDS` in `release_canary.py`, and the test reads the `targets` job limit from `canary.yml`. The unit names come from `prepare` in `release_canary.py`. Searched: `workflows/hard-eng.yml`, `shards`, `timeout` and `PASS` in `.hooks/`, `release_canary.py`, `setup.py`, `.github/` and `tests/`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer asked for a rule of at most 100 commits for each project, for a fix or a close of each open Hard Eng issue, and for an audit and a fix of repeated CI checks, also in the code that each project installs.

Decided:

1. A shard job that is proved elsewhere writes `coverage/shards/<N>/proven.txt` and prints the reuse line. The upload step runs for each shard and ignores an empty folder.
2. The gate job runs no proof. It passes when any shard sent `proven.txt`, and prints which shard proved the tree. Otherwise it merges the reports as before.
3. No job is skipped. A skipped job would break the success check of the gate job and the skipped-check rule of the reuse lookup.
4. The template at `.github/hard-eng.yml` starts as a copy of the base workflow, with the double quotes. The own workflow is then generated from it, not picked.
5. The format gate of the shipped files covers the template, the generated shard form and the PR text workflow.
6. A path in the command of a sharded gate stays refused. The refusal also names the `--option=value` form, because `--cov src` is refused when `src` is a folder.
7. The Dart move comes first. Without it, the shards check puts `.hooks/gate_config.py` at 1,006 lines.
8. The canary entry comes after the template move. Before the move, the own workflow is the template.
9. The release gate gets one total limit below the 65-minute limit of the `canary` job, with a rerun step. The other two places of cause (3) stay as they are.
10. A release PR summary line says that the next step checks the push run of `develop`. The line "No installed file changed" stays for a push or PR that changed no installed file.
11. A passed new project prints its unit names in its pass line, in the order that they ran.

## Acceptance + steps

Constraints: the limit is 1,000 lines for each file. On the trial branch, `.hooks/gate_config.py` has 967 lines after the Dart move, `.hooks/hard-eng.py` 927 with the marker, `.hooks/reports.py` 992 and `.hooks/ci_setup.py` 911. `.hooks/update.py` (1,000), `.hooks/plans.py` (999), `.hooks/shipping.py` (944) and `.hooks/change_size.py` (508) get no added line. A change to `.hooks/update.py` or `.hooks/plans.py` first moves a block out. Each commit passes the line limit on its own.

Slice 1, the Dart move (`.hooks/gate_config.py`, `.hooks/dart_boundaries.py`, `setup.py`):

- [ ] The two Dart settings checks are in `.hooks/dart_boundaries.py` → N/A — a move; the proof is that the Dart tests pass with only import lines changed

Slice 2, the `shards` field (`.hooks/gate_config.py`):

- [ ] A tests gate accepts a whole number from 2 to 16 and refuses each other value → `tests/test_shards.py::test_shards_is_a_whole_number_from_2_to_16_on_a_tests_gate`
- [ ] A Stop check with shards set loads no shard module → `tests/test_gate_speed.py::test_stop_with_shards_set_loads_no_shard_module`

Slice 3, the `--shard` flag (`.hooks/ci_jobs.py`, `.hooks/hard-eng.py`, `.hooks/shards.py`):

- [ ] The flag takes a shard number, `rest` or `merge`, and refuses other values → `tests/test_shards.py::test_the_shard_flag_takes_a_number_rest_or_merge`
- [ ] `rest` drops only the tests gates that have shards → `tests/test_shards.py::test_rest_drops_only_the_tests_gates_that_have_shards`
- [ ] A numbered shard keeps its tests gate and the installs above it → `tests/test_shards.py::test_a_shard_keeps_its_tests_gate_and_the_installs_above_it`
- [ ] A gate with fewer shards runs nothing in a higher shard → `tests/test_shards.py::test_a_gate_with_fewer_shards_runs_nothing_in_a_higher_shard`
- [ ] With no shards, `rest` runs every gate and a numbered shard runs none → `tests/test_shards.py::test_without_shards_rest_runs_every_gate_and_a_shard_runs_none`
- [ ] Shards need a command that runs pytest directly → `tests/test_shards.py::test_shards_need_a_direct_pytest_command`

Slice 4, a numbered shard runs its own files (`.hooks/shards.py`, `.hooks/hard-eng.py`):

- [ ] The split gives each file to the lightest shard, largest file first → `tests/test_shards.py::test_split_gives_each_file_to_the_lightest_shard_largest_first`
- [ ] A shard runs only the files that pytest collects for it → `tests/test_shards.py::test_a_shard_runs_only_the_files_pytest_collects_for_it`
- [ ] A shard keeps its reports apart and skips the coverage minimum → `tests/test_shards.py::test_a_shard_keeps_its_reports_apart_and_skips_the_coverage_minimum`
- [ ] A shard with no files starts no pytest → `tests/test_shards.py::test_an_empty_shard_starts_no_pytest`
- [ ] The time of a shard does not shorten the limit of the full gate → `tests/test_shards.py::test_shard_time_does_not_shorten_the_full_gate_limit`

Slice 5, the gate job merges the reports (`.hooks/shards.py`, `.hooks/reports.py`, `.hooks/hard-eng.py`):

- [ ] The gate job applies the coverage minimum to the merged report → `tests/test_shards.py::test_the_gate_job_applies_the_coverage_minimum_to_the_merged_report`
- [ ] The gate job refuses a missing shard report, with the step → `tests/test_shards.py::test_the_gate_job_refuses_missing_shard_reports`
- [ ] Merged coverage equals one full run → `tests/test_shards.py::test_merged_shard_coverage_equals_one_full_run`
- [ ] The merged test report holds each case and skip, and skipped plan tests still fail → `tests/test_shards.py::test_the_gate_job_fails_skipped_plan_acceptance_tests`
- [ ] The gate job runs with bare `python3` and only Git on the path → `tests/test_shards.py::test_the_gate_job_runs_with_bare_python`
- [ ] Only the gate job skips the tool setup → `tests/test_shards.py::test_only_the_gate_job_skips_tool_setup`

Slice 6, the template move (`.github/hard-eng.yml`, `.hooks/ci_setup.py`, `hard-eng.gates.json`, `tests/conftest.py`):

- [ ] A project without shards gets the one-job workflow from the template → `tests/test_shard_workflow.py::test_a_project_without_shards_gets_the_one_job_workflow`
- [ ] A release tree from before the move still gives the template → `tests/test_shard_workflow.py::test_an_older_release_tree_still_gives_the_template`
- [ ] The template has the double-quoted lines, and an old workflow gets them at the next update → `tests/test_bun_workflow_migration.py::test_an_old_workflow_gets_double_quoted_mise_switches`
- [ ] The format gate of the shipped files covers the template and each installed workflow → `tests/test_gate_tools.py::test_the_shipped_format_gate_covers_each_installed_workflow`
- [ ] The template takes its runner from the variable → `tests/test_runner_variable.py::test_shipped_workflows_take_their_runner_from_the_variable`
- [ ] The template holds the one release age → `tests/test_tool_execution.py::test_release_age_has_one_value`

Slice 7, the canary trigger (`release_canary.py`):

- [ ] An edit of the own workflow alone starts no canary, and an edit of the template does → `tests/test_release_canary.py::test_only_changes_to_installed_files_need_a_canary_run`

Slice 8, two sharded gates (`.hooks/shards.py`):

- [ ] Two tests gates with shards in one package are refused → `tests/test_shards.py::test_two_sharded_gates_in_one_package_are_refused`

Slice 9, a path in a sharded command (`.hooks/shards.py`):

- [ ] A path in the command of a sharded gate is refused, with the full step → `tests/test_shards.py::test_a_path_in_the_gate_command_is_refused_because_every_shard_would_run_it_whole`
- [ ] An option value that names a folder, such as `--cov src`, gets the refusal with the `--option=value` form → `tests/test_shards.py::test_an_option_value_that_names_a_folder_gets_the_equals_form_in_the_refusal`

Slice 10, a worker count (`tests/test_shards.py`):

- [ ] A worker count in the pytest settings leaves the files of a shard exact → `tests/test_shards.py::test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact`

Slice 11, the shard form of the workflow (`.hooks/shards.py`, `.hooks/ci_setup.py`, `.agents/skills/he/references/gates.md`):

- [ ] Setup writes the checks job, one tests job for each shard and the required `hard-eng` job → `tests/test_shard_workflow.py::test_shards_split_the_ci_job_into_checks_tests_and_the_gate_job`
- [ ] The shard jobs take the budget timeout and the gate job keeps five minutes → `tests/test_shard_workflow.py::test_shard_jobs_inherit_the_budget_timeout_and_the_gate_job_keeps_five`
- [ ] A changed shard count rewrites the shard list → `tests/test_shard_workflow.py::test_a_changed_shard_count_rewrites_the_shard_list`
- [ ] An update splits an installed one-job workflow → `tests/test_shard_workflow.py::test_update_splits_an_installed_one_job_workflow`
- [ ] A customised or split workflow gets a note and no shards → `tests/test_shard_workflow.py::test_a_split_workflow_gets_a_note_and_no_shards`
- [ ] Setup refuses shards on a gate that does not run pytest → `tests/test_shard_workflow.py::test_setup_refuses_shards_on_a_gate_that_does_not_run_pytest`

Slice 12, the proof of a shard (`.hooks/shards.py`, `.hooks/hard-eng.py`):

- [ ] A shard job that reuses a passed commit prints the reuse line and writes its marker; the checks job writes none → `tests/test_ci_usage.py::test_a_shard_job_that_reuses_a_passed_commit_marks_its_shard`
- [ ] The gate job passes on a marker, prints the shard, and never starts the proof, also with no `uv` → `tests/test_ci_usage.py::test_the_gate_job_takes_a_shard_proof_and_runs_none_itself`
- [ ] With no marker and no reports, the gate job still refuses → `tests/test_shards.py::test_the_gate_job_without_a_shard_proof_still_needs_each_report`
- [ ] The upload step runs for each shard and ignores an empty folder → `tests/test_shard_workflow.py::test_shards_split_the_ci_job_into_checks_tests_and_the_gate_job`
- [ ] A run that selects no package passes in the gate job with no marker and no report, and starts no download → `tests/test_shard_workflow.py::test_a_run_that_selects_no_package_passes_in_the_gate_job_with_no_download`

Slice 13, an edit under `.github` (`hard-eng.gates.json`):

- [ ] An edit of the template or the own workflow selects the package checks → `tests/test_shard_workflow.py::test_an_edit_under_github_selects_the_package_checks`

Slice 14, six shards for this repository (`hard-eng.gates.json`, `.github/workflows/hard-eng.yml`):

- [ ] The own workflow equals the generated shard form of six shards → `tests/test_shard_workflow.py::test_own_workflow_is_the_generated_shard_form`

Slice 15, time limits of the canary (`release_canary.py`):

- [ ] A push lists each new project when a lookup stalls past the total limit → `tests/test_canary_reuse.py::test_a_push_runs_the_new_projects_when_a_lookup_stalls`
- [ ] The lookup limit of a push is at most half the limit of the `targets` job → `tests/test_canary_reuse.py::test_a_develop_push_reuses_the_new_project_jobs_of_the_merged_pr`
- [ ] The release gate ends with a rerun step before the limit of the `canary` job → `tests/test_canary_reuse.py::test_the_release_gate_ends_before_the_canary_job_limit`

- [ ] The update project of the canary fails when an update writes a shard workflow into a project with no shards → `tests/test_release_canary.py::test_the_update_target_refuses_a_shard_workflow_in_a_project_without_shards`

Slice 16, the summary of a release PR (`.github/workflows/canary.yml`):

- [ ] A release PR summary names the next step, and only a push or PR with no installed file prints "No installed file changed" → `tests/test_canary_reuse.py::test_the_canary_summary_says_no_installed_file_changed_only_when_none_changed`

Slice 17, the pass line of a new project (`release_canary.py`):

- [ ] A passed new project names each unit that ran, such as `full check` and `project lint` → `tests/test_release_canary.py::test_a_passed_new_project_names_each_unit_that_ran`

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 6dde3718, the rebase merge of PR 577. On that commit the required CI checks passed on 2026-11-11: each push run reused the pass of the PR head on the same files, and that head passed the full check and each new-project job. `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on this branch, with this plan as the only change: exit 0.
Execution: one builder on Sonnet in its own worktree builds slices 1 to 14 in this order, with a failing test before each behavior and each static gate command in its brief. The push limit of slice 15 is built with its failing test first and joins as its own commit; the release gate limit and slices 16 and 17 follow. The coordinator reviews each slice. Then a new reviewer on Opus reads the joined change, the independent review runs on the final commit, and the Complete check runs once.

## Risks + recovery

- A run that selects no package sends no artifact. Recovery: the gate job starts no download in that case, and slice 12 proves it; the plan does not depend on what the download action does with no match.
- After the template move, the old workflow path in a release tree holds the six-shard file of this repository. An installed project runs the setup file of the new release for its update plan, so it reads the new template path. Recovery: the canary's update project installs the last release and updates to the candidate, and slice 15 makes it fail on a shard workflow; a run on a local release host from the last release proves it before the push.
- The artifact action pins were not checked against GitHub. Recovery: the PR's own run uses them, and a failed upload or download fails the tests or gate job.
- A self-hosted runner has a `python3` older than 3.12 first on its path. Then the gate job stops with "Hard Eng needs Python 3.12 or later". Recovery: that text names the step; the `impact` step already needs the same version.
- Code in a PR could write a marker file during its tests. Recovery: the same PR code runs every job, so the marker adds no trust that the job result does not have.
- A reused push still starts each job. Recovery: each job prints the reuse line and ends after its setup steps.

## ux_reference

N/A — check rules, CI files and printed lines with no visual surface.

## Verification

Result: Pending
Evidence: Pending — the static gates, the whole suite and the Complete check on the joined branch, and the review results.
E2E: N/A — no user journey changes; each behavior is a check, setup or CI result that its test runs directly, and the real shard run is in Delivery.
Retro: Pending — written at task end.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` and `canary` checks green, then the release into `main`. The PR's own run gives the real CI time of the shard form against the old single job. One rerun of the green run proves that a second attempt uploads and downloads again.
