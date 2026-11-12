# Fix the faults of audit round fourteen: a Stop that checks no commit, a mutation report that cannot run, and failures that name no step

Status: Ready

## Outcome + scope

An audit of the released code ran in sealed copies of five real projects and in two areas of new fixtures. Each fault that it reproduced in normal use is fixed here, with a failing test first. A Stop in a checkout with no record of the session checks the commits that are not pushed. The mutation report of a Python package leaves the performance suite out of its test runs. A test gate whose command wrote no JUnit report says so and names the step. A JavaScript package can keep the support files of its browser tests in the folder that its Playwright settings name. A Dart analysis that fails for files that code generation did not make yet names the step and the role `generated`. A changed Dart `part` file brings its library into the first run of a quick check, so the lints of an analyzer plugin see it. A full check with no `--base` writes the pass record, and a Stop also reuses a record whose base is older than its own, so the Stop after such a check takes under a second where it took 9 to 17 s. Non-goals: no change to a project of a user, no new gate, no new option, and no fix for a fault that the audit rates as rare.

## Repository context

Owners: `.hooks/agent_hooks.py` owns the Stop: `completion` reads the session record with `saved_session`, and `session_scope` chooses the base and the commit of HEAD. `.hooks/mutation.py` owns the mutation report: `targets` selects the packages, `ADAPTERS` holds one adapter for each language, and `configure_mutmut` writes the settings of mutmut when the project has none. `.hooks/reports.py` owns `completed_tests`, which reads the test report of a gate, and `validate_performance_junit`, which uses it for the performance gate. `.hooks/coverage_sources.py` owns `source_roots` and `require_listed_sources`, the rule "code is outside its sources"; `.hooks/project_setup.py` calls `source_roots` to write the `sources` list of a new package. `.hooks/gate_config.py` owns `TEST_FOLDERS` and `nonproduction_source`; `.hooks/plans.py` owns `_is_test` and a second list, `TEST_DIRECTORIES`. `.hooks/gate_runner.py` owns `run_limited_gate`, which prints the output of a gate and its PASS or FAIL line; `.hooks/process_group.py` owns the notes that go under a FAIL line (`stopped_note`, `parallel_hint`), `INSTALL_ROLES` and the record of a full pass: `clean_start` and `record_pass` write it, `covering_minutes` reads it for the Stop. `.hooks/gate_schedule.py` owns `changed_dart`, the list of files of the first run of a Dart analysis.
Same cause: four causes. (1) A Stop judges a change from a base that leaves work out. Earlier fixes: `session_scope` moved the base of a recorded session to the commits that are not pushed (rounds eleven to thirteen; helped). No fix covered a session with no record: `saved_session` then gives HEAD, and each commit of the session is behind that base. Other places, searched: the push check (its base is the remote branch, not the record), the Codex Stop (the same function), the session start (writes the record) and `checked_changes` (writes a record after the first pass, with the base that the Stop used; fixed by the same change). (2) A failure that names no step. Earlier fixes: the text for a missing Python coverage report in `python_coverage` and the notes of the tool directories (both helped). Other places, searched in `.hooks/reports.py` and `.hooks/gate_runner.py`: the JUnit report of a test gate and of a performance gate (slice 3), a Dart analysis with missing generated files (slice 5); the Dart test report and the Xcode summary are written by the gate runner or named by their own tool, so they are not hit. (3) A test tool that changes how fast the code runs. Only mutmut is hit: it puts a wrapper on each function of the source paths, so a timed test fails. Stryker changes only the changed lines, and the Dart tool changes the text of one line for each run; both run the tests at their normal speed. (4) A rule calls test support code production code. Earlier fix: file names such as `*.spec.ts` and the folders of `TEST_FOLDERS` (helped). The sources rule did not know the folder that a Playwright settings file names. Other places, searched: `_is_test` in `.hooks/plans.py` judges a path with no file read and keeps its own list of folders; slice 4 gives the two lists one owner. (5) The first run of a Dart analysis judges a file with less than the package run sees. Earlier fixes, round thirteen: no first run for a changed settings file, a missing file, a file outside the package or a folder name (helped). A changed `part` file was not covered: analysed alone it is no library, and the rules of an analyzer plugin run for a library. Other places, searched: a changed library with unchanged parts (the analyzer reads the parts with it), a generated part that Git tracks (the same rule covers it). (6) A Stop pays again for proof that exists. Earlier fix, round thirteen: the record of a full pass (helped for a check with `--base`). `clean_start` writes no record for a check with no base, and the Stop asks for the exact base. Other places, searched: the push check (its base is the tip of the base branch, which is the judged base of a plain check on a branch that was rebased, so it reuses the new record with no change) and CI (writes no record).
Single source: `gate_config.TEST_FOLDERS` becomes the one list of the folder names that hold test code; `plans.TEST_DIRECTORIES` is merged into it in slice 4 (searched: `TEST_FOLDERS`, `TEST_DIRECTORIES`, `"__tests__"` in `.hooks/`; no third copy). `INSTALL_ROLES` in `.hooks/process_group.py` stays the one list of the roles that a quick check runs until they pass; the new failure note names the role from that list. The form "an argument of a performance gate whose last part is `performance`" has one reader today, in `.hooks/gate_runner.py`; slice 2 reads the same form through one shared function. The text of a missing JUnit report gets one owner, `completed_tests`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer said that the builder makes the decisions. On 2026-11-12 the maintainer said that each change must give a real gain and follow best practice, with no change that only renames.

1. A fault is fixed here when the audit reproduced it in normal use and a failing test shows it. A fault that the audit rates as rare is recorded, not built.
2. Decision 10 of round thirteen is reversed. That decision made a project move the support files of its browser tests under a folder named `tests`. A move of that kind gives the project no gain: the folder that a Playwright settings file names in `testDir` is the standard place for those files. Hard Eng now reads that setting. The sealed copy of one real project holds 2 such folders and 6 support files; after slice 4 the rule names neither folder there.
3. Only the string form of `testDir` counts (`testDir: "./e2e"`, with one folder name). A computed value is not read; the project then lists the folder or moves it, as today. A named folder is test code only when each code file in it is a test file by its name, or is reached by relative imports from such a file or from a path that the settings file names (`globalSetup`, `globalTeardown`). So a package with `testDir: "./src"` and tests beside its application code keeps `src` as a source: its entry file is reached by no test. A support file that no test reaches keeps the folder outside the sources, as today.
4. The role `generated` stays the contract for the code generation of a package. A quick check that runs each writer gate one time in a new checkout was rejected: in the five sealed copies the writer roles hold 4 application builds, 3 test scripts and 9 boundary scripts. Slice 5 makes the contract known at the point of the failure.
5. The mutation report leaves out the suite that the performance gate of the package names. A project with its own mutmut settings keeps them without change, as today.
6. Recorded, not built: a setup rerun writes a gates file again when a hand edit changed only its layout (rare); a time weight for the shard split (about 20 s of 5 min).
7. A plain full check records the base that it judged from. A Stop reuses a record of its commit when the base of the record is its own base or an ancestor of it: the full check then judged each change that the Stop would judge, and more. The Stop asks Git that one question only when the record holds its commit and another base. The push check keeps its exact match.
8. A changed `part` file with `part of '<file>';` adds that library file to the first run. A `part of <name>;` directive gives no first run, so the package run decides.
9. Open: an auditor reported that a fix commit on the update branch needs a plan because the size line counts the files of the update. A separate run in a fixture decides if this is a fault and where its cause is. If it is, one slice is added to this plan before the build ends.

## Acceptance + steps

Slice 1: a Stop with no session record.

- [ ] A Stop of a session that has no record in the checkout checks each commit that is not pushed: with one such commit and a clean tree it runs the check from the parent of that commit, and it does not answer "no code checks run" → `tests/test_stop_checks.py::test_a_stop_with_no_session_record_checks_the_commits_that_are_not_pushed`
- [ ] The record that this Stop writes after a pass holds that base, so the next Stop with no change answers "unchanged since last passing check" → `tests/test_stop_checks.py::test_the_first_pass_of_a_stop_with_no_record_keeps_the_base_of_the_commits_that_are_not_pushed`
- [ ] A session with a record keeps its base and starts no more Git processes → `tests/test_stop_checks.py::test_a_branch_on_a_shared_branch_checks_only_its_own_commits`, `tests/test_stop_checks.py::test_a_stop_asks_git_for_no_answer_that_it_holds`

Slice 2: the mutation report of a Python package.

- [ ] The settings that the report writes for mutmut hold `--ignore=` for each suite that a performance gate of the package names, and none when the package has no such gate → `tests/test_mutation.py::test_mutmut_settings_leave_out_each_performance_suite_of_the_package`
- [ ] A real run on a package whose performance test fails under mutmut prints the result line of the report, not "could not run" → `tests/test_mutation.py::test_the_python_mutation_report_runs_when_a_performance_test_fails_under_mutmut`

Slice 3: a test gate with no JUnit report.

- [ ] A tests gate and a performance gate whose command passed and wrote no JUnit report fail with one line that names the report path and the step, and with no `[Errno` text → `tests/test_reports.py::test_a_missing_junit_report_names_the_report_and_the_step`
- [ ] That failure stays in the class "the gate did not run": `adopt` records no debt line for it → `tests/test_reports.py::test_a_missing_junit_report_is_never_recorded_as_debt`

Slice 4: the test folder of Playwright.

- [ ] A JavaScript package whose Playwright settings file names `./e2e` as `testDir` passes the sources rule with support files in `e2e`; setup does not list that folder in `sources` → `tests/test_typescript_sources.py::test_the_test_folder_of_a_playwright_settings_file_is_test_code`
- [ ] A folder that no settings file names, a folder that only a computed `testDir` names, and a named folder with a support file that no test reaches still fail the rule with the same text as today → `tests/test_typescript_sources.py::test_a_folder_that_no_playwright_setting_names_is_still_outside_the_sources`
- [ ] A package with `testDir: "./src"` and tests beside its application code keeps `src` in the `sources` list that setup writes, and the rule still names `src` when the list leaves it out → `tests/test_typescript_sources.py::test_application_code_beside_playwright_tests_stays_a_source`
- [ ] A check of a package with no code outside its sources reads no Playwright settings file → `tests/test_typescript_sources.py::test_a_package_with_no_code_outside_its_sources_reads_no_playwright_settings_file`
- [ ] One list of test folder names: a support file under `integration_test/` is test code for the rules that use `_is_test` → `tests/test_change_size.py::test_a_support_file_of_an_integration_test_is_test_code`

Slice 5: a Dart analysis with missing generated files.

- [ ] A failed Dart analysis whose output holds `uri_has_not_been_generated` prints one note that says to run the code generation of the package and to give that gate the role `generated`; the Stop text of that failure holds the note → `tests/test_quick_dart_analysis.py::test_a_dart_analysis_with_missing_generated_files_names_the_step`
- [ ] A failed Dart analysis with other findings, and a passed analysis, print no such note → `tests/test_quick_dart_analysis.py::test_a_dart_analysis_with_other_findings_prints_no_generation_note`

Slice 6: a changed Dart `part` file.

- [ ] A changed file with `part of '<file>';` brings that library file into the first run of the Dart analysis of its package → `tests/test_quick_dart_analysis.py::test_a_changed_part_file_brings_its_library_into_the_first_run`
- [ ] A changed file with `part of <name>;`, or with a library file that is missing or outside the package, gets no first run → `tests/test_quick_dart_analysis.py::test_a_part_file_with_no_library_file_gets_no_first_run`

Slice 7: the pass record of a plain full check.

- [ ] A full check with no `--base` that passes on a clean tree writes the pass record with the commit that it judged from; a check in CI, a partial check and a check at another plan stage write none, as today → `tests/test_stop_reuse.py::test_a_full_check_with_no_base_writes_the_pass_record`
- [ ] A Stop reuses a record of its commit whose base is an ancestor of its own base, and says that the base was earlier; a record with a base that is no ancestor makes the Stop run its check → `tests/test_stop_reuse.py::test_a_stop_reuses_a_full_pass_from_an_earlier_base`
- [ ] A Stop with a record of its exact commit and base starts no more Git processes than today → `tests/test_stop_checks.py::test_a_stop_asks_git_for_no_answer_that_it_holds`

Proof on real projects and speed.

- [ ] In the sealed copy of the real project with 2 Playwright test folders, the sources rule names neither folder, with no file moved → N/A — no test can hold a private project; the run is recorded in Verification with counts only
- [ ] Session start and Stop are not slower: old against new, two runs each, in a pair of copies → N/A — a timing on one machine; the numbers are recorded in Verification

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on the commit that adds this plan: exit 0. No package reads a change that holds only the plan, so the check ran the secret scan and reused the proof of the branch point. The branch point is `develop` at 40f8c7d8. Its tree is the tree of the head of PR 583, whose checks passed (25 of 25); the Complete check of round thirteen passed on that tree (20 gates, 4,045 tests), and the run on `develop` passed after the merge.
Execution: two builders in two worktrees, then one reviewer that did not write the code. Builder A: slices 1, 7, 5 and 6, in that order (`.hooks/agent_hooks.py`, `.hooks/process_group.py`, `.hooks/gate_runner.py`, `.hooks/gate_schedule.py`). Builder B: slices 2, 3 and 4 (`.hooks/mutation.py`, `.hooks/reports.py`, `.hooks/coverage_sources.py`, `.hooks/gate_config.py`, `.hooks/plans.py`). The two sets of files do not meet. The coordinator joins the commits on the task branch, runs the static gates and the focused tests, the independent review, and the Complete check one time.

## Risks + recovery

- A Stop with no record now checks commits of an earlier session that were not pushed. That is the safe side: such commits passed no push check. Recovery: revert the commit of slice 1.
- `.hooks/plans.py` holds 1,000 lines, the limit. Slice 4 takes one line out and puts one in; a longer change fails the size gate and is then made smaller.
- The `--ignore=` option reaches pytest through the mutmut setting `pytest_add_cli_args`. The real run of slice 2 proves the path form; if a later mutmut release renames the setting, that test fails.
- The note of slice 5 depends on the code name that the Dart analyzer prints. If the name changes, the note is not printed and the failure is as it is today.
- A record with an earlier base could pass a Stop that a rule "not worse than the base" would block, when a pushed commit made the base better than the branch point. The full check in CI judges from the branch point too, so the Stop is not weaker than CI. Recovery: revert the commit of slice 7.
- The first run reads each changed Dart file one time to find a `part of` line. The cost is measured old against new and recorded in Verification.
- Each slice is its own set of commits; revert them newest first to undo.

## ux_reference

N/A — no visible surface changes; each change is a hook result, a check result or a printed line.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no user journey changes; each behavior is a hook result, a check or a printed line that its test runs directly.
Retro: Pending

Delivery target: Merge
Delivery: Pending — the PR checks pass on the final commit, `ship` passes its ready stage, the rebase merge into `develop` and the release merge into `main` are done, and the `main` run passes.
