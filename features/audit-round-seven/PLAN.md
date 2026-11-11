# Fix the faults that the round 7 audit reproduced in normal use: checks that judge only uncommitted work, parent groups that read a child group, and steps that cannot be done

Status: Ready

## Outcome + scope

A `check` gives the same plan result for committed and uncommitted work. A parent package group and a child package group do not fail each other. A step that a message names can be done in the state where the message prints. One load of the gate settings starts fewer Git commands. Each item was reproduced by a round 7 audit run, a research run or a real run of the coordinator, on `develop` 133bb25b.

The bar for this round: build a fix for a wrong pass, a wrong fail, or a step that cannot be done. Fix minor wording only where its owner file is open for another fix.

Non-goals:

- Choices for the maintainer, not built: `adopt` in a project with no remote refuses after setup commits the install, because the install commit is already the default branch, and a fix needs a change of the debt rule; a `Removed test:` record does not cover one assertion that is removed from a test that stays (this round fixes the message only); `adopt` can record a refusal that Hard Eng raises before a tool runs, for example the strict Pyrefly refusal after a settings change, and only the performance suite refusal is closed here; an old Complete plan with a small edit still covers new work.
- A Python project with code under `src/` and no build system fails the imports gate right after the install, with Import Linter's own line. Import Linter has no path option; a fix needs an environment value in the gate command.
- A second top-level package under `src/` fails the dependencies gate with deptry's own line until a setup rerun adds its name.
- An existing uv project that does not declare pytest gets "Cannot find module pytest" from the types gate with no step. This round fixes new projects.
- A test that runs the module in a child process gets no mutation result. One removed parametrize case passes the lost-assertion rule. A Swift test cannot be named in a `Removed test:` record.
- Python code below a package of another language is read by the lint and format gates of the Python root only; the annotations, types, dead-code and coverage gates do not read it.
- A project that still has the release before round 6 installed: its rerun plans the checkout with that release, so a new package gets no group until the update lands. The rerun says nothing about that package.
- A plain `check` with a clean tree passes committed work with no plan while the default branch does not hold the install. Round 6 kept that result on purpose.
- Rare cases that no run reached in normal use: a ticked acceptance test in a file that pytest does not collect; a Stop with no session start record; an update failure that names the wrong place when the gates file has a conflict; `ship --stage cleanup --worktree` with a path that does not exist.
- Minor items whose owner file this round does not open: a rerun fetches the installed release two times; a failed fetch prints the raw Git command; a refused update prints each line of a long result at each session start; the Dart strict settings refusal names no file.

## Repository context

Owners: `validate_plans` in `.hooks/plans.py` owns the stage and the plans that a check judges, with `size_verdict` and `update_written` in `.hooks/change_size.py`. `verify` in `.hooks/shipping.py` owns the order of the ship refusals. `packages_for` in `.hooks/gate_config.py` owns which group a changed file selects, and `language_groups` in `.hooks/ci_jobs.py` owns the language filter. `prepare_command` and `run_limited_gate` in `.hooks/hard-eng.py` own the command that a gate runs, with `.hooks/python_setup.py` for the Python commands. `validate_fallow` in `.hooks/fallow_report.py` owns the Fallow notes. `repair_checkout` and `prepare_update` in `.hooks/update_runner.py` own what a setup rerun writes and says. `record` and `judge` in `.hooks/debt.py` own what debt holds. `lost_assertions` in `.hooks/comments.py` owns the lost-assertion message. `failure_context` in `.hooks/failures.py` owns the tool failure count. `build` in `new_project.py` and the starter under `.agents/starters/python` own a new Python project. `.hooks/mutation.py` owns the mutation report. `lock_stamp` in `.hooks/process_group.py` owns the install mark. `load_groups` and `generated_sources` in `.hooks/gate_config.py` own the load of the gate settings.
Same cause: eleven causes. (1) A plan rule reads its scope from `HEAD` when no base is given. Round 6 fixed this cause for the size question only and wrote "the set of changed files that the other plan rules read stays as it is" (helped for a change with no plan; no effect for a Draft or Ready plan with committed code, because the round 6 table had no column for committed code with a plan). One place: `validate_plans`. `plan_tests` gets its plans through `released_plans` and needs no change; `validate_comments`, `validate_suppressions`, `validate_decisions` and `require_shrink` already fall back to the branch point. Search for texts that name a plain `check` as a step: `command grep -rn "hard-eng.py check" .hooks setup.py README.md .agents/skills/he*` gives the Stop lock message, the tools message of the quick check, the session start lines for PyYAML and for a broken configuration, the last line of setup and the README table; in a build the first two now name the build form, and the others reach a refusal that names it. (2) A plan counts as the plan of this task when its path changed. One place: `applicable_plans`, called by `validate_plans` and `plan_tests`. An exact move is fixed here; an edited old plan is a Non-goal. (3) The size rule counts changes that the task did not make. Round 5 and round 6 took out a proven update only on a clean tree that holds only update commits (helped for a clean update branch; no effect with a fix commit or an uncommitted fix). Places: a merge of the base in progress, a fix on the update branch, leftover files at cleanup (judged before the clean rule), and the reason text of a branch that installs Hard Eng. The other callers of `update_in_diff` (`proven_elsewhere`, the package narrowing and the freshness skip) must keep the strict form: with the loose form a file that the update did not write would pass with no gate. (4) Each place works out the relation of a parent group and a child group on its own. Earlier fixes: the Biome child rule, the file list of the Python types gate, the round 6 install mark of a workspace root with no language, and `selected_services` for a root with no language (each helped for its own place). Places fixed here: `language_groups` drops a root with no language; `packages_for` picks the nearest folder of any language; the pytest and deptry commands of a Python group read the folders of child groups; `validate_fallow` uses no relation. Places not changed: ruff and Semgrep of a Python root read a child folder a second time with no wrong result; a Dart parent reads nested packages on purpose; `owned_files` keeps its rule. (5) A rerun plans as if each planned file lands, and writes a part of the plan. Round 6 made the rerun write the gates file and the missing project files (helped for a missing group; hurt for the workflow gates, whose workflow files the rerun does not write). Places: `repair_checkout` (the workflow gates, the claim in its note, the note lost when the update build fails) and the strict Pyrefly refusal, which names no file for a `pyproject.toml` that the rerun leaves alone. The other files that a first install edits and a rerun leaves alone already get a message that names the file or the block, or are Non-goals. (6) `adopt` records a refusal that Hard Eng raises before the tool runs. Round 6 changed when `adopt` refuses (helped). Place fixed: the performance suite refusal. Search: each `raise ValueError` that `prepare_command` and `prepare_reports` reach; the others are a Non-goal. (7) A message names a step that cannot be done in the state where it prints. Rounds 4 to 6 fixed such messages one at a time (helped for those messages). Here: the `Removed test:` text for a test that stays, `pre-push --help`, the path in the performance message, and the lock message in a build. (8) mutmut gives a function the module name `__main__` when a test runs the module with `runpy`, so that test kills no mutant. Places: the Python starter test, and the report text for a mutant that no test ran. (9) The install mark of the quick check does not see a removed install folder. Round 6 added the lock stamp (helped for a changed lock file). One place: `lock_stamp`. (10) The tool failure hook counts by the error text, and `exit=1` lines are not in its noise pattern. One place: `EXIT_CODE_OR_SPACE_OR_DIGIT`. (11) One load of the gate settings asks Git for file attributes four times. One place: `load_groups` and the callers of `generated_sources` below it.
Single source: `default_branch_point` in `.hooks/plans.py` stays the one owner of the branch point; `judged_point` in `.hooks/change_size.py` replaces `judges_branch` and returns that point, and the size point during a merge is worked out there from the same references. `update_written` in `.hooks/change_size.py` is the one owner of "paths that a verified update wrote" for the plan rule and the size rule; `installed_update_paths` stays the owner for the gate narrowing; both prove by content through `release_installed`. The sentence "During the build, run this check with --plan-stage Ready" has one constant, used by the Draft refusal and the Ready refusal. The table of source file suffixes for each language moves from `production_files` in `.hooks/hard-eng.py` to `.hooks/gate_config.py`, where `production_files` and `packages_for` read it; `validate_file_sizes` keeps its own list, because it also holds file types that no language group owns. The rule "a child group of the same language with a gate of the same role" gets one function; the Biome child rule calls it and keeps its own test of the command. The strict Pyrefly rule gets one owner in `.hooks/python_setup.py`, called by setup and by the types gate; the two copies of today differ, and setup takes the rule of the gate. The lock file names stay in `LOCKFILES`; the install folder names are new and have one tuple in `.hooks/process_group.py`. Searched for copies: `command grep -rn "merge-base\|MERGE_HEAD\|node_modules\|\.dart_tool\|preset\|check-unannotated-defs" .hooks setup.py`.
Escaped bug: every item is on the base branch and passed each gate on its PR. The test gate should have caught each one. Each gets a case that fails on `develop` before its fix. Three items are faults of round 6 code: the workflow gates that a rerun writes, the claim and the lost note of the rerun, and the install mark after a removed folder. Their round 6 tests had no project with a shipping block and no update build that fails, and the install mark tests changed only lock files.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn.
Decided (1): with no `--base`, when Hard Eng is on the branch point with the default branch, the plan rules of `check` use that branch point as their base. Committed code and uncommitted code then get the same stage and the same plans. This reverses the round 6 sentence that the changed files of the other plan rules stay as they are. A first install that the default branch does not hold, and a branch with no branch point, keep the result of today. The Stop hook and pre-push pass a base and do not change.
Decided (2): a plain `check` still requires Complete for code changes, as the plan checks reference says. The Ready refusal of a check with no given stage adds the sentence that the Draft refusal has: during the build, run the check with `--plan-stage Ready`. The Stop lock message and the tools message of the quick check name that form when it is the one that runs the gates.
Decided (3): a changed plan whose text equals a plan that the base holds, and that the branch removed from its old path, is not the plan of new work. Git is asked only when the changed set holds a plan path that is gone.
Decided (4): while a merge is in progress, the size rule measures from the merge base of the default branch with both merge parents. A merge of the base then adds nothing to the size; a merge of another branch still adds its files. `MERGE_HEAD` is found with a file read, also in a linked worktree.
Decided (5): the size rule and the plan rule take out the paths that a verified update wrote also when the branch holds a later fix commit or an uncommitted fix. The proof stays by content, so an installed file with a hand edit still counts. A change with no installed path starts no update lookup. `proven_elsewhere`, the package narrowing and the freshness skip keep the strict form.
Decided (6): a branch that installs Hard Eng itself gets the reason "this branch installs Hard Eng" in its size line, not the name of an installed file. The rule does not change: the install needs a plan, as the setup text says.
Decided (7): `ship` applies the clean checkout rule before the plan rule at each stage.
Decided (8): at run time, the pytest and deptry commands of a Python group leave out the folder of each child Python group that has a gate of the same role. The child list comes from the whole gates file, not from the selected groups. The gates file does not change, and a `--ignore` in a gate command is still refused.
Decided (9): a changed file whose suffix belongs to another language than its nearest group also selects the nearest group above it of that language. The rule only adds groups.
Decided (10): `--only-language` keeps the lockfiles gate of each folder above a kept group, with or without a language.
Decided (11): Fallow's `node-modules-missing` note is accepted for a workspace member that declares no dependency of any kind, when a folder above it has `node_modules`. A real Fallow 3.41.0 run in such a member gave the same findings with and without the member's own folder: an import of a package that is not installed is reported in both states.
Decided (12): setup and the types gate use one strict Pyrefly rule, and its message names the file and the lines to add. A project whose existing settings hold a key that the gate refuses is now refused at setup, with that message; before, its first check failed with a message that named no file.
Decided (13): a rerun does not write the workflow gates into a checkout that has no workflow file; its note says that the update brings the gates with the files. The note names the written files and makes no claim about packages. The note is printed also when the update build fails after the write.
Decided (14): the missing performance suite refusal is never recorded as debt and never matches a debt entry. A budget failure stays recordable, as today. A project that already holds the entry gets the failure with its two steps; after one of them, `adopt` drops the entry.
Decided (15): the lost-assertion message says that a `Removed test:` record covers a whole test and that the test name is the function name alone. The rule does not change.
Decided (16): `--new python` declares pytest as a dev dependency before the lock, and the starter test uses the `capsys` fixture of pytest and calls `main()` directly. The starter then proves the types gate with a pytest import, and no starter test runs the module under another name.
Decided (17): the mutation report lists a mutant that no test ran under its own line, "no test reached this function", not under "the tests still pass".
Decided (18): the install mark of a package group also holds which of `.venv`, `node_modules` and `.dart_tool` exist in its folder. A removed folder ends the mark.
Decided (19): one load of the gate settings reads the Git attributes of the listed files one time; each rule in that load reads from it.

## Acceptance + steps

Slice 1, the stage of a check with no base (`.hooks/plans.py`, `.hooks/change_size.py`, `.hooks/agent_hooks.py`, `.hooks/tool_setup.py`):

- [ ] `check` with no `--base` gives the same result for committed and uncommitted code: a Draft plan fails with the Draft line, a Ready plan fails with the Ready line, a Complete plan runs the gates, and a big change with no plan fails with the size line → `tests/test_plans.py::test_a_check_with_no_base_judges_committed_code_as_it_judges_uncommitted_code`.
- [ ] `check --plan-stage Complete` on a clean tree fails committed work that has no plan of its own when an old Complete plan exists → `tests/test_plans.py::test_an_old_complete_plan_does_not_cover_committed_work_under_a_plan_stage_check`.
- [ ] A first install that the default branch does not hold keeps its result → `tests/test_change_size.py::test_a_check_with_no_base_passes_a_first_install_that_the_base_lacks`.
- [ ] A check with no base on a verified update branch needs no plan while another plan is open → `tests/test_update_pr.py::test_a_check_with_no_base_needs_no_plan_on_a_verified_update_branch`.
- [ ] The Ready refusal of a check with no given stage names the build form → `tests/test_plans.py::test_a_ready_plan_with_code_edits_names_the_build_form_of_the_check`.
- [ ] The Stop lock message names `check --plan-stage Ready` while a build is in progress and the plain `check` at other times → `tests/test_stop_checks.py::test_the_lock_message_names_the_check_that_runs_gates_in_a_build`.
- [ ] The tools message of the quick check names the build form → `tests/test_tool_setup.py::test_the_missing_tools_message_names_the_build_form_of_the_check`.

Slice 2, a moved plan (`.hooks/plans.py`, `.hooks/change_size.py`):

- [ ] A plan that only moved does not cover new work: new code beside it fails with the size line, and a new Draft plan beside it fails with the Draft line → `tests/test_plans.py::test_a_moved_plan_does_not_cover_new_work`.
- [ ] A branch that only moves a plan passes → `tests/test_plans.py::test_a_branch_that_only_moves_a_plan_passes`.

Slice 3, the size of a change (`.hooks/change_size.py`, `.hooks/update.py`, `.hooks/shipping.py`):

- [ ] During a merge of the base, in conflict or staged, in a main checkout and in a linked worktree, the size counts only the task's change → `tests/test_change_size.py::test_a_merge_of_the_base_in_progress_does_not_count_the_base_changes`.
- [ ] During a merge of another branch, its files count → `tests/test_change_size.py::test_a_merge_of_another_branch_in_progress_counts_its_files`.
- [ ] A committed fix on a repair update and an uncommitted fix on an update are judged without the update's files → `tests/test_update_pr.py::test_a_fix_on_the_update_branch_is_judged_without_the_update_files`.
- [ ] A hand edit of an installed file on the update branch stays big → `tests/test_update_pr.py::test_a_hand_edit_of_an_installed_file_on_the_update_branch_stays_big`.
- [ ] `check` runs the gates on an update branch that holds an uncommitted file that the update did not write → `tests/test_update_pr.py::test_an_update_branch_with_another_file_still_runs_the_gates`.
- [ ] A size question for a change with no installed path starts no Git command for the update lookup → `tests/test_change_size.py::test_a_change_with_no_installed_path_starts_no_update_lookup`.
- [ ] The size line of a branch that installs Hard Eng gives the install as the reason → `tests/test_change_size.py::test_a_branch_that_installs_hard_eng_names_the_install_as_the_reason`.
- [ ] `ship` refuses a merged small task that has a leftover file with the clean checkout line → `tests/test_ship_cleanup.py::test_a_leftover_file_in_a_merged_small_task_gets_the_clean_checkout_line`.

Slice 4, a parent group and a child group (`.hooks/hard-eng.py`, `.hooks/python_setup.py`, `.hooks/gate_config.py`, `.hooks/dependency_graph.py`, `.hooks/ci_jobs.py`, `.hooks/fallow_report.py`):

- [ ] The pytest and deptry commands of a Python group leave out each child Python group that has a gate of the same role, also when the child is not selected; a child with no such gate stays read → `tests/test_python_setup.py::test_a_python_parent_leaves_out_child_groups_that_have_the_same_gate`.
- [ ] The run-time exclusion passes the test filter rule, and a `--ignore` in the gate command is still refused → `tests/test_tool_execution.py::test_the_child_exclusion_passes_the_test_filter_rule`.
- [ ] A changed Python file below a group of another language also selects the Python group above it → `tests/test_affected_selection.py::test_a_file_of_another_language_also_selects_the_group_that_reads_it`.
- [ ] `--only-language` keeps the lockfiles gate of a workspace root that has no language → `tests/test_apple_jobs.py::test_a_language_filter_keeps_the_install_of_a_root_with_no_language`.
- [ ] Fallow passes a workspace member that declares no dependency and has no `node_modules` of its own when a folder above has one; a member with a declared dependency fails, and so does a member with no install above it → `tests/test_fallow_sdk.py::test_a_member_with_no_dependencies_needs_no_install_folder_of_its_own`.
- [ ] Joined proof with the real tools: a uv workspace whose root has its own code passes the root dependencies gate after a first install, and the member's test runs one time → N/A — a real install with real tools in a sealed fixture; the commands and results go in Verification.

Slice 5, what a rerun writes and says (`.hooks/python_setup.py`, `.hooks/hard-eng.py`, `.hooks/update_runner.py`):

- [ ] The strict Pyrefly refusal names the file and the lines to add → `tests/test_python_setup.py::test_the_strict_pyrefly_refusal_names_the_file_and_the_lines`.
- [ ] Setup refuses each Pyrefly setting that the types gate refuses → `tests/test_python_setup.py::test_setup_refuses_the_pyrefly_settings_that_the_types_gate_refuses`.
- [ ] A rerun leaves the workflow gates to the update when the checkout has no workflow file, and its note says so → `tests/test_update_runner.py::test_a_rerun_leaves_the_workflow_gates_to_the_update_when_the_checkout_has_no_workflow`.
- [ ] The note about written files is printed when the update build fails after the write, and it makes no claim about packages → `tests/test_update_runner.py::test_a_failed_update_build_still_names_the_files_that_the_rerun_wrote`.

Slice 6, small fixes (`.hooks/debt.py`, `.hooks/comments.py`, `.hooks/hard-eng.py`, `.hooks/failures.py`, `new_project.py`, `.agents/starters/python`, `.hooks/mutation.py`, `.hooks/process_group.py`, `README.md`):

- [ ] `adopt` refuses the missing performance suite, and a debt entry for it no longer passes the gate → `tests/test_debt.py::test_the_missing_performance_suite_is_never_debt`.
- [ ] A performance budget failure is still recorded → `tests/test_debt.py::test_a_performance_budget_failure_is_still_recorded`.
- [ ] The lost-assertion message says what a `Removed test:` record covers and which name it wants → `tests/test_comments.py::test_the_lost_assertion_message_says_what_the_record_covers`.
- [ ] `pre-push --help` prints the help and reads no input → `tests/test_ship_actions.py::test_pre_push_help_prints_the_help`.
- [ ] The missing performance suite message names a file that exists → `tests/test_tool_execution.py::test_the_missing_performance_suite_message_names_an_existing_file`.
- [ ] Three failed commands whose error text holds only exit codes are not one repeated error → `tests/test_failures.py::test_exit_code_lines_alone_never_count_as_a_repeated_error`.
- [ ] `--new python` declares pytest as a dev dependency before the lock → `tests/test_new_project.py::test_python_declares_pytest_for_the_types_gate`.
- [ ] The Python starter test imports pytest and runs no module under another name → `tests/test_new_project.py::test_the_python_starter_test_calls_main_directly`.
- [ ] The mutation report does not say that the tests pass for a mutant that no test ran → `tests/test_mutation.py::test_a_mutant_that_no_test_ran_is_not_reported_as_passing_tests`.
- [ ] A removed install folder ends the install mark → `tests/test_quick_check.py::test_a_removed_install_folder_drops_the_install_mark`.
- [ ] The README row for "Agent stops" names the install of the first quick check → N/A — a text change; the Reader check covers it.

Slice 7, speed (`.hooks/gate_config.py`):

- [ ] One load of the gate settings starts one Git attributes read → `tests/test_gate_speed.py::test_a_config_load_reads_the_git_attributes_one_time`.
- [ ] Each rule in the load sees the same generated files as before → `tests/test_gate_speed.py::test_one_attributes_read_gives_each_rule_the_same_generated_files`.
- [ ] No hook is slower: one Stop with nothing changed, one Stop with a change and one session start, old against new → N/A — a measurement on two copies with compiled modules, alternating runs and medians, with counts of Python calls and Git starts; the numbers go in Verification.

Text changes: each changed message, the README row and each changed reference line get a Reader check by an agent that did not write them; the result goes in Verification.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 133bb25b, the merge of round 6. On that commit the required CI checks passed on 2026-11-11. `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch, with this plan as the only change: exit 0.
Execution: builders on Sonnet, each with one failing test before each fix and each static gate command in its brief. Builder A builds slices 1, 2 and 3 in order in one worktree, because they share `.hooks/plans.py` and `.hooks/change_size.py`. Builder B builds slice 4 in its own worktree at the same time; it shares no file with builder A. The coordinator joins both, a code reviewer and a test reviewer on Opus read the joined change, and `challenge` runs on that commit. Then one builder builds slices 5 and 6, and one builds slice 7; they share no file. Five files are at or near the 1,000 line limit (`.hooks/plans.py` 999, `.hooks/hard-eng.py` 998, `.hooks/project_setup.py` 998, `.hooks/agent_hooks.py` 996, `.hooks/gate_config.py` 966): slice 4 moves the suffix table out of `.hooks/hard-eng.py`, slice 5 moves the Pyrefly rule out of it, and no slice adds a module file. First slice: slice 1.

Dependencies: slice 2 and slice 3 build on the `validate_plans` of slice 1. Slice 5 and slice 6 both edit `.hooks/hard-eng.py` and have one builder. Slices 4 and 7 both edit `.hooks/gate_config.py`; slice 7 starts after slice 4 is joined.

## Risks + recovery

- A plain `check` on a branch with committed code and a Draft or Ready plan now fails where it passed. Pre-push already fails that branch. The refusal names the build form.
- A project with a Pyrefly setting that the types gate refuses is now refused at setup. Its first check failed before.
- A project that holds a debt entry for a missing performance suite now fails the performance gate until it adds a suite or records the exception. The message names both steps.
- The pytest command of a Python parent no longer runs the tests of a child group that has its own tests gate. Uncertainty: deptry may read its exclude option one time only. Cheapest check: the joined proof with the real tool; if false, the two patterns go into one expression.
- The size rule trusts the content proof of an update with a fix beside it. The proof is the one that the clean update branch uses today.
- The install mark of each checkout ends one time after this change, because its stored form changes; the next quick check runs each install again.
- The starter test and the pytest dev dependency change new Python projects only. Uncertainty: `uv add` needs the package index, as each other new stack does. Cheapest check: the greenfield Python job of the canary.
- Recovery for any slice: revert its commits.

## ux_reference

N/A — hook, command and message changes with no visual surface.

## Verification

Result: Pending
Evidence: Pending — focused tests for each fix, the static gates, the Reader check, the timing, `challenge` on the candidate commit, then the Complete check one time.
E2E: N/A — no user journey changes; each behavior is a hook, command or setup result that its test runs directly, and the joined proof runs a first install and the gates in a real workspace fixture.
Retro: Pending — written at the task end.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` and `canary` CI checks green. The PR holds the result of the independent review. Then the release into `main`.
