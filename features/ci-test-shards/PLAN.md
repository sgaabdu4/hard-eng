# Split the CI tests over shard jobs, and fix three canary faults

Status: Ready

## Outcome + scope

A project can split its pytest tests gate over CI shard jobs with `"shards": N`, and this repository runs its tests in six shards. Shards are opt-in for each project. A project without the field keeps the one-job workflow. The required check keeps its name, `hard-eng`. Three canary faults are fixed: one total time limit for the GitHub lookups of a push, a false summary line on a release PR, and a pass line that names no unit. An audit of the released code reproduced faults in normal use, and slices 18 to 27 fix them: a retry form that passed, a commit cap step that failed, a Stop check that blocked a committed reformat, a wrong test hint, three messages with no usable step, a debt check that counted Ruff's advice, Biome settings that setup read or wrote in part, two freshness steps that could not run, and a mutation run that could not start. A review of the shard change found faults in it, and slices 28 to 32 fix them.

Non-goals:

- Trusted code for the CI jobs: a later plan.
- The cheaper file walk: a later plan.
- The rule for an edited old finished plan that passes today's rules: a later plan.
- Shards for a tests gate that does not run pytest directly. Setup refuses it.
- Fewer runners on a reused push. Each job still starts and prints the reuse line.
- A copy check of JavaScript, Dart and Swift test files: a later plan. The tools skip test files by default, and an update would fail on old copies.
- One Git start in place of two in the config load: a later plan.

## Repository context

Owners: `.hooks/shards.py` (new) owns the shard split, the shard runs, the report merge, the proof marker and the shard form of the workflow. `.hooks/gate_config.py` owns the check of the `shards` field. `.hooks/ci_jobs.py` owns the `--shard` flag. `.hooks/hard-eng.py` owns `check` and the calls into the shard module. `.hooks/dart_boundaries.py` gets the two Dart settings checks from `.hooks/gate_config.py`. `.hooks/ci_setup.py` owns the template path and the workflow migrations. `.github/hard-eng.yml` (new) is the template that setup installs. `.github/workflows/hard-eng.yml` becomes the generated shard form of this repository. `hard-eng.gates.json` owns the gates of this repository and the format gate of the shipped files. `release_canary.py` and `.github/workflows/canary.yml` own the new-project jobs, the canary trigger and the release gate. `.hooks/retry_forms.py` owns the retry forms. `.hooks/change_size.py` owns the commit cap text and the judged stage of a plan. `.hooks/process_group.py` owns the notes on how a gate's process ended, now with the parallel hint. `.hooks/coverage_sources.py` owns the names and the reader of the coverage settings files. `.hooks/debt.py` owns the comparison of old findings. `.hooks/untrusted_input.py` owns the edit of a project's Biome settings, and `.hooks/gate_config.py` the JSON layout that setup writes. `.hooks/poetry_freshness.py` and `.hooks/uv_freshness.py` (new) own the printed freshness steps. `.hooks/mutation.py` owns the start of the mutation tool.
Same cause: fifteen causes. (1) One test job sets the CI time of a project. Earlier fix: the reuse rule of round ten skips checks that passed on the same files; it helped only for repeated runs. Other places: none; the Swift split moves only Swift gates to macOS. (2) A job that runs with no tools makes a decision that needs a tool. The gate job runs bare `python3`, and the scaffold-only proof of an update PR starts `uv` through `update_plan`. With no `uv` on the path, the gate fails while the shard jobs proved the tree. Earlier fix: none. Other places, searched: the `impact` step runs the same proof with bare `python3`, but it catches the error and the full check follows. Fixed here: the gate job runs no proof and takes the proof of a shard job. (3) The time limit of a call equals or passes the limit of its job, so GitHub ends the job before the fallback. Earlier fix: the lookups of a push got one total limit of 120 seconds (this plan). Other places, searched in `release_canary.py` and each workflow: the release gate waits up to 3,600 seconds, then makes more lookups of up to 300 seconds each, and the `canary` job limit is 65 minutes (3,900 seconds); fixed here. The new-project steps have a limit of 3,600 seconds in a 60-minute job, and a gate of `check` in CI has a limit of `ci_seconds` (600) in a 10-minute job. Not changed: in both, the job fails either way, and no fallback runs after the limit; only the stop text is lost. The `pr text` and `release source` jobs set no time limit on a call. (4) A summary line claims a result that a later step decides. Earlier fix: none. Other places, searched in `canary.yml` and `release_pr_gate`: the release gate prints the same words only when the diff holds no installed file, which is true there. (5) A pass line hides what ran. Earlier fix: the `project lint` unit of round ten. Other places: the agent units already print their own name. (6) The switch-off rule knows the retry forms one by one. Earlier fix: the `reruns` key and the `--retries` option. Other places, searched in `.hooks/retry_forms.py`: the forms for commands, pytest settings, test files and JavaScript configs; the audit found no other form that passes. A review of the fix then found two more forms of the same key: the colon of an ini file and spaces in the table header. Both are refused now. A second review then found that the rule knew four names of pytest settings files, where pytest 9 reads seven. One list, `PYTEST_FILES`, now holds the seven names in pytest's order. (7) A printed step cannot run as printed. The commit cap step named no lease push, the Poetry step named a version that fits only the running Python, and the uv step was one line with a placeholder. Earlier fix: none. Other places, searched: the Bun, Dart and Flutter steps in `.hooks/freshness.py` are whole commands with the package names; not changed. A review of the fix then found two more faults. The uv step dropped the marker and the extras of the declared entry. The Poetry floor could go below the declared lower bound. Both are fixed here. (8) The Stop check and the full check read the changed plans in two ways. `judged_stage` took the changed files from the base only, and `judged_plans` adds the released plans. Earlier fix: round ten made an uncommitted reformat of an old plan count as unchanged. Other places, searched: each caller of `changed_files` in `.hooks/change_size.py`, `.hooks/plans.py`, `.hooks/comments.py` and `.hooks/gate_config.py`; no other caller judges an old plan. (9) Advice is printed from the exit code alone, before the report says what failed. Earlier fix: a run with no tests gets no parallel hint. Other places, searched: `stopped_note` reads only the stop signal, which is its whole fact. (10) A message names no file, or a file that the project cannot change. Earlier fix: none. Other places, searched: each `raise ValueError` in `.hooks/dart_boundaries.py` and the "Coverage report omits" text in `.hooks/reports.py`; the JavaScript and Dart coverage settings can have the same gap, the audit did not reproduce it, and they are not changed. A review of the fix then found that the omit sentence printed for any `omit` line. It now prints only when an entry of the file that coverage.py reads matches a missing file. (11) The debt comparison reads each output line of a tool as a finding. Earlier fix: masked numbers and count words. Other places: only Ruff prints fix advice that changes with a nearby edit; a list line of another tool stays a finding, and a test holds that. A review of the fix then found that the test for Ruff matched the word `ruff` anywhere in the command, so a `ruff format` gate lost its diff lines. One helper now matches only a `ruff check` command. (12) Setup read and wrote a project's Biome settings in part: the layout came from the root file only, and the ignore list got only `.hooks`. Earlier fix: the `!.hooks` entry. Other places, searched: `fallow_ignores_hooks` adds `.hooks` for Fallow; Fallow follows the Git ignore file, and setup lists `.hard-eng/` and `coverage/` there. A review of the fix then found two faults. The entry for each folder named `coverage` also hid source folders of that name; the list now names only the report folder of each package. The edit took its layout from the local file only; it now uses the reader of the JSON layout. (13) One tool starts the package manager by its bare name. Earlier fix: none. Other places, searched for a Poetry start in `.hooks/`: the gate commands, the interpreter lookup and the freshness dry run pass through `managed_command`. (14) A setting of the project reaches a shard run and changes its result: a `-v` changed the form of the test listing, and the project's own `fail_under` failed each part. Earlier fix: the worker count of slice 10. Other places, searched with real pytest: `-vv`, `-q` and `-ra` in the settings leave the listing as it is. A second review then found that the minimum of the pytest settings came from a text search of five files. It missed a list of two items and `pytest.toml`, and it read tox environments, scripts of other tools and comments. The reader now takes the one file that pytest reads, from the package folder up, and only its `addopts`. (15) A part counts as the whole: a local shard run recorded a full pass, a removed `shards` field kept the split workflow, and a setup rerun at the installed release wrote an existing file again only when it was a rule file or the gates file, so a new workflow form waited for the next release. Earlier fix: none. Other places, searched: `partial` in `check` now holds each run that is not the full check (quick, one language, no dependents, related tests, a shard); in `repair_installation`, the other installed workflow, `pr-text.yml`, does not depend on the gates file. A second review then found that a hand-edited split workflow stayed with no note after the field was removed; setup now prints one.
Single source: the `shards` field has one check, `validate_shards` in `.hooks/gate_config.py`. The shard job texts, the artifact pins, the marker name and the shard note have one owner, `.hooks/shards.py`. The template path has one owner, `TEMPLATE` in `.hooks/ci_setup.py`, with `TEMPLATE_BEFORE_MOVE` for a release tree from before the move; each migration reads it through `template_text`. The two quoted workflow lines have one owner, the template; the migration names the same two lines. The lookup limit has one owner, `PUSH_LOOKUP_SECONDS` in `release_canary.py`, and the test reads the `targets` job limit from `canary.yml`. The unit names come from `prepare` in `release_canary.py`. Searched: `workflows/hard-eng.yml`, `shards`, `timeout` and `PASS` in `.hooks/`, `release_canary.py`, `setup.py`, `.github/` and `tests/`. The names of the coverage settings files have one list, `COVERAGE_FILES`, and one reader, `coverage_file`, in `.hooks/coverage_sources.py`; the `omit` sentence and the minimum of the merged shards use both. The commit cap step has one text, `JOIN_COMMITS` in `.hooks/change_size.py`. The entries that setup adds to a project's Biome settings have one owner, `biome_entries` in `.hooks/untrusted_input.py`. The Biome formatter options have one reader, `biome_formatters` in `.hooks/gate_config.py`. The test for a `ruff check` command has one owner, `ruff_check` in `.hooks/debt.py`; `without_fixes` in `.hooks/hard-eng.py` uses it. The names of the pytest settings files have one list, `PYTEST_FILES` in `.hooks/retry_forms.py`; the retry rule and the minimum reader use it. The reader of a TOML or INI settings file has one owner, `file_sections` in `.hooks/coverage_sources.py`. The step for a nested Dart settings file has one text, `NESTED_STEP` in `.hooks/dart_boundaries.py`. The names of the rule files have one set for the two uses in `.hooks/update.py`, `RULE_FILES`; `.hooks/agent_hooks.py` and `.hooks/gate_config.py` each keep their own set of the same three names, because `gate_config` cannot import `update` and `agent_hooks` is at the line limit for one more import.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer asked for a rule of at most 100 commits for each project, for a fix or a close of each open Hard Eng issue, and for an audit and a fix of repeated CI checks, also in the code that each project installs.

Decided:

1. Each numbered shard job writes one marker in `coverage/shards/<N>/`: `proven.txt` with the reuse line when the tree is proved elsewhere, else `ran.txt`. So the upload of a shard is never empty, and the gate job always downloads.
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

Constraints: the limit is 1,000 lines for each file. After the last slice, `.hooks/gate_config.py` has 987 lines, `.hooks/hard-eng.py` 935, `.hooks/reports.py` 985 and `.hooks/ci_setup.py` 911. `.hooks/update.py` has 994 lines after slice 31, which joins two copies of the rule file names. `.hooks/plans.py` (999) and `.hooks/shipping.py` (944) get no added line. A change to `.hooks/update.py` or `.hooks/plans.py` first moves a block out. Each commit passes the line limit on its own.

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
- [ ] A run that selects no package leaves a marker in each shard, and the gate job passes on the markers that it downloads → `tests/test_shard_workflow.py::test_a_run_that_selects_no_package_leaves_a_marker_in_each_shard_for_the_gate_download`

Slice 13, an edit under `.github` (`hard-eng.gates.json`):

- [ ] An edit of the own workflow selects the package checks → `tests/test_shard_workflow.py::test_an_edit_under_github_selects_the_package_checks`

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

Slice 18, the retry count of pytest-retry (`.hooks/retry_forms.py`, `.hooks/comments.py`):

- [ ] A `retries` count inside a pytest table is refused at its line, and the same key of another table passes → `tests/test_comments.py::test_a_retry_count_in_a_pytest_table_fails_at_its_line`
- [ ] The colon form of an ini file, a table header with spaces and a count in `pytest.toml`, `.pytest.toml` or `.pytest.ini` are refused too → `tests/test_comments.py::test_a_retry_count_in_a_pytest_table_fails_at_its_line`
- [ ] A rerun key or option in `pytest.toml`, `.pytest.toml` or `.pytest.ini` is refused → `tests/test_comments.py::test_an_added_retry_fails_naming_file_line_and_form`

Slice 19, the commit cap step (`.hooks/change_size.py`):

- [ ] The warning from 80 commits prints the empty diff check and the lease push → `tests/test_change_size.py::test_a_full_check_warns_from_80_commits_and_never_refuses`
- [ ] The refusal over the cap prints the same step → `tests/test_ship_commits.py::test_ready_refuses_a_pr_over_the_commit_cap`

Slice 20, a committed reformat of an old plan (`.hooks/change_size.py`):

- [ ] A committed white space reformat of an old plan counts as unchanged when the check starts from the new head, and a committed word change still needs today's fields → `tests/test_planning_handoffs.py::test_a_committed_reformat_of_an_old_plan_counts_as_unchanged_from_the_new_head`

Slice 21, the parallel hint (`.hooks/process_group.py`, `.hooks/hard-eng.py`):

- [ ] A parallel run where no test failed gets no hint, and a run with a failed test or an unreadable report keeps it → `tests/test_report_findings.py::test_a_parallel_run_where_no_test_failed_gets_no_parallel_hint`

Slice 22, the Dart settings messages (`.hooks/dart_boundaries.py`):

- [ ] A nested settings file that lacks the settings is named, with its step → `tests/test_dart_config.py::test_a_nested_settings_file_that_lacks_the_settings_is_named_with_its_step`
- [ ] A fault in a file of an included package names the include to remove → `tests/test_dart_config.py::test_a_fault_in_an_included_package_names_the_include_to_remove`

Slice 23, the coverage omit setting (`.hooks/coverage_sources.py`, `.hooks/reports.py`, `.hooks/shards.py`):

- [ ] A Python file that an `omit` setting hides names that setting and its file → `tests/test_line_coverage.py::test_a_python_file_that_an_omit_setting_hides_names_that_setting`
- [ ] An `omit` setting that does not hide the file adds no sentence: other files, a file that coverage.py does not read, a broken file → `tests/test_line_coverage.py::test_an_omit_setting_that_does_not_hide_the_file_adds_no_omit_sentence`

Slice 24, Ruff's fix advice in the debt check (`.hooks/debt.py`, `.hooks/hard-eng.py`):

- [ ] Fix advice that Ruff adds or drops for an old finding is no change → `tests/test_debt.py::test_a_fix_hint_that_ruff_adds_or_drops_for_an_old_finding_is_no_change`
- [ ] A list line of another tool is still a finding → `tests/test_debt.py::test_a_list_line_of_another_tool_is_still_a_finding`
- [ ] A new format fault beside an old one is a finding → `tests/test_debt.py::test_a_new_format_fault_beside_an_old_one_is_a_finding`
- [ ] A `ruff check` through `uvx` leaves out the fix advice too → `tests/test_debt.py::test_a_ruff_check_through_uvx_leaves_out_the_fix_advice_too`

Slice 25, a project's Biome settings (`.hooks/gate_config.py`, `.hooks/untrusted_input.py`):

- [ ] The JSON layout follows a local file that the Biome settings extend → `tests/test_json_layout.py::test_an_extended_local_file_sets_the_json_layout`
- [ ] The root formatter wins over the extended one → `tests/test_json_layout.py::test_the_root_formatter_overrides_the_extended_one`
- [ ] An extended package name keeps the default layout, and a file that extends itself ends → `tests/test_json_layout.py::test_a_file_that_extends_itself_ends`
- [ ] Setup adds `.hooks`, `.hard-eng` and the root report folder to the list, with `**` first in an empty list → `tests/test_biome_entries.py::test_setup_keeps_the_project_biome_run_away_from_the_hooks_folder`
- [ ] An older install gets only the entries that it lacks → `tests/test_biome_entries.py::test_setup_adds_only_the_entries_that_an_older_install_lacks`
- [ ] Setup prints the step when it cannot edit the settings → `tests/test_biome_entries.py::test_setup_prints_a_step_when_it_cannot_edit_the_biome_settings`
- [ ] The list names the report folder of each package that is not at the root, and a second run changes nothing → `tests/test_biome_entries.py::test_the_biome_list_names_the_report_folder_of_each_package`
- [ ] The planned gates file wins over the file on disk → `tests/test_biome_entries.py::test_the_planned_gates_file_wins_over_the_one_on_disk`
- [ ] An older install gets only the package folders that it lacks → `tests/test_biome_entries.py::test_an_older_install_gets_only_the_package_folders_it_lacks`
- [ ] The edit takes its indent and line width from the extended file → `tests/test_biome_entries.py::test_the_biome_edit_takes_its_layout_from_the_extended_file`

Slice 26, the freshness steps (`.hooks/poetry_freshness.py`, `.hooks/uv_freshness.py`):

- [ ] The Poetry step is the add that its dry run proved → `tests/test_freshness_steps.py::test_the_poetry_step_is_the_add_its_dry_run_proved`
- [ ] A split lock floors each entry at its oldest locked version → `tests/test_freshness_steps.py::test_a_split_lock_floors_each_entry_at_its_oldest_locked_version`
- [ ] A capitalised name finds its entry on a split lock → `tests/test_freshness_steps.py::test_a_capitalised_name_finds_its_entry_on_a_split_lock`
- [ ] The uv step raises each entry in its package and section → `tests/test_freshness_steps.py::test_the_uv_step_raises_each_entry_in_its_package_and_section`
- [ ] A dynamic dependency list gets the hand step → `tests/test_freshness_steps.py::test_a_dynamic_dependency_list_gets_the_hand_step`
- [ ] A single uv project gets a command that runs as printed → `tests/test_freshness_steps.py::test_a_single_uv_project_gets_a_command_it_can_run_as_printed`
- [ ] The uv step keeps the marker and the extras of the declared entry → `tests/test_freshness_steps.py::test_the_uv_step_keeps_the_marker_and_the_extras_of_the_declared_entry`
- [ ] The Poetry floor is never below the declared lower bound → `tests/test_freshness_steps.py::test_the_poetry_floor_is_never_below_the_declared_lower_bound`

Slice 27, the mutation run of a Poetry project (`.hooks/mutation.py`):

- [ ] The mutation tool starts through the managed command, as the gates do → `tests/test_mutation.py::test_the_mutation_run_starts_poetry_the_way_the_gates_do`

Slice 28, a local shard run (`.hooks/hard-eng.py`):

- [ ] A local `--shard` run records no full pass → `tests/test_shards.py::test_a_local_shard_run_records_no_full_pass`

Slice 29, the test listing of a shard (`.hooks/shards.py`):

- [ ] A `-v` or `-vv` in the project's pytest settings leaves the files of a shard exact → `tests/test_shards.py::test_a_verbose_setting_in_the_pytest_settings_leaves_the_shard_files_exact`
- [ ] A listing that ends well and names no file is refused → `tests/test_shards.py::test_a_listing_that_names_no_file_is_refused`

Slice 30, the project's own coverage minimum (`.hooks/shards.py`, `.hooks/coverage_sources.py`, `.hooks/retry_forms.py`):

- [ ] A shard does not apply the coverage minimum of the project → `tests/test_shards.py::test_a_shard_does_not_apply_the_coverage_minimum_of_the_project`
- [ ] The gate job applies that minimum to the merged total and names the place that sets it → `tests/test_shards.py::test_the_gate_job_applies_the_coverage_minimum_of_the_project_to_the_merged_total`
- [ ] The minimum comes from the command, then the pytest settings, then the first coverage settings file → `tests/test_shard_coverage_minimum.py::test_the_minimum_comes_from_the_command_then_the_pytest_settings_then_the_first_coverage_file`
- [ ] The total counts branches when the report has them → `tests/test_shard_coverage_minimum.py::test_the_total_counts_branches_when_the_report_has_them`
- [ ] The verdict equals the verdict of the coverage tool → `tests/test_shard_coverage_minimum.py::test_the_verdict_is_the_one_of_the_coverage_tool`
- [ ] The minimum of the pytest settings is in the `addopts` of the one file that pytest reads: a list of two items, `pytest.toml`, the native table, no tox environment, no script of another tool, no comment → `tests/test_shard_coverage_minimum.py::test_the_minimum_of_the_pytest_settings_is_in_the_addopts_of_the_file_that_pytest_reads`
- [ ] The pytest settings of a parent folder apply to the package → `tests/test_shard_coverage_minimum.py::test_the_pytest_settings_of_a_parent_folder_apply_to_the_package`
- [ ] A settings file that cannot be read is named → `tests/test_shard_coverage_minimum.py::test_a_settings_file_that_cannot_be_read_is_named`
- [ ] The printed total equals the one of the coverage tool → `tests/test_shard_coverage_minimum.py::test_the_printed_total_is_the_one_of_the_coverage_tool`

Slice 31, the way back to one job (`.hooks/shards.py`, `.hooks/update.py`):

- [ ] Setup writes the one-job workflow back when no gate holds `shards` → `tests/test_shard_workflow.py::test_removing_shards_gives_the_one_job_workflow_back`
- [ ] A workflow that is not the generated form stays as it is, and setup prints a note → `tests/test_shard_workflow.py::test_removing_shards_leaves_a_workflow_that_is_not_the_generated_form`
- [ ] A setup rerun at the installed release writes the workflow form that the `shards` field asks for: split, a new count, and one job again → `tests/test_shard_rerun.py::test_a_setup_rerun_writes_the_workflow_form_that_the_shards_field_asks_for`

Slice 32, the gate job and the matrix (`.hooks/shards.py`, `.github/workflows/hard-eng.yml`):

- [ ] The gate job runs after a failed job and merges only after two successes → `tests/test_shard_workflow.py::test_the_gate_job_runs_after_a_failed_job_and_merges_only_after_two_successes`
- [ ] One failed shard does not cancel the others → `tests/test_shard_workflow.py::test_shards_split_the_ci_job_into_checks_tests_and_the_gate_job`
- [ ] The refusal for a missing shard report says to rerun all jobs → `tests/test_shards.py::test_the_gate_job_refuses_missing_shard_reports`

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 6dde3718, the rebase merge of PR 577. On that commit the required CI checks passed on 2026-11-11: each push run reused the pass of the PR head on the same files, and that head passed the full check and each new-project job. `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on this branch, with this plan as the only change: exit 0.
Execution: one builder on Sonnet in its own worktree builds slices 1 to 14 in this order, with a failing test before each behavior and each static gate command in its brief. The push limit of slice 15 is built with its failing test first and joins as its own commit; the release gate limit and slices 16 and 17 follow. The coordinator reviews each slice. Then a new reviewer on Opus reads the joined change, the independent review runs on the final commit, and the Complete check runs once. The audit fixes of slices 18 to 27 were built by the coordinator and by two more builders on Sonnet, each in its own worktree, and joined by cherry-pick. A reviewer on Opus read the shard change, and one more builder fixed its findings in slices 28 to 32. A second reviewer on Opus read the audit fixes. A reader on Opus who did not write the text compared the old and the new shard sentences of `.agents/skills/he/references/gates.md` two times; each sentence that the reader quoted was reworded. A third reviewer on Opus read the shard fixes. The coordinator fixed its findings and compared the minimum reader with real pytest and pytest-cov on 15 settings layouts.

## Risks + recovery

- A run that selects no package: each numbered shard job writes its marker, so the upload and the download always have a file. Recovery: slice 12 proves that the gate job passes on the markers; the plan does not depend on what the download action does with no match.
- A run that a person cancels can leave the required `hard-eng` job skipped, because its `if` line is false on a cancel, and GitHub's documents say that a skipped job reports success. The Apple gate job has the same line. Recovery: Hard Eng's own `ship` refuses a skipped required check, and a rerun gives the real result. An `always()` line was not used: its job would run on each replaced push and hold the next run back.
- The reader of a project's coverage minimum reads three places: the tests command, the `addopts` of the one settings file that pytest reads, and the first coverage settings file of the package folder. It does not read `-c`, `-o addopts`, `PYTEST_ADDOPTS`, `--cov-config`, `COVERAGE_RCFILE` or `--cov-precision`. A coverage section that holds only unknown options ends its search, where coverage.py goes on to the next file. Recovery: Hard Eng's own minimum of 70% still applies.
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
