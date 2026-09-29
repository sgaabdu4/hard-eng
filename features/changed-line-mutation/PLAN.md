# Report mutants the tests miss on changed lines at every push

Status: Complete

## Outcome + scope

After pre-push checks pass, Hard Eng mutates the changed production lines of each JavaScript, Python and Dart package and lists the mutants the tests miss, as `file:line original → mutated`. The report never blocks the push, stops after 180 seconds and skips text-only mutants. `python3 .hooks/hard-eng.py mutation --base <ref>` checks a snapshot of HEAD and then reports without a limit.

Non-goals:
- Blocking a push or failing CI on survivors: some survivors are equivalent mutants that need judgement.
- Mutating uncommitted work: mutation_test edits source in place, so it only runs in a snapshot.
- Hard Eng's own `.hooks`: mutmut imports mutated code by module name, which `.hooks` is not; its pushes print that mutation could not run.
- Per-test selection for Flutter suites: each mutant runs the package's tests, so slow suites reach the 180-second limit and point to the command.

## Repository context

Owners:
- `.hooks/ship_actions.py` `pre_push`: checks each pushed revision in a disposable worktree; mutation runs there after the check passes.
- `.hooks/hard-eng.py` `production_files`: the production sources of each package, which bound what is mutated.
- `.hooks/tool_setup.py` `provision_batch`: installs the latest Stryker through mise like the other npm tools.
- `.hooks/project_setup.py` `python_gate_command`: the uv or Poetry prefix the Python gates use.
- Research: mutmut 3.8 mutates whole functions selected by name glob; StrykerJS takes `file:start-end` ranges and excludes `StringLiteral`; mutation_test 1.8.1 takes an XML line whitelist and `--exclude-strings`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for mutation testing on changed code in this PR, and agreed to a report-only run at every push plus an on-demand command for a deeper run.

## Acceptance + steps

- [x] Only new-side lines of added or modified files are mutated, as merged ranges → `test_changed_lines_become_the_ranges_the_tools_mutate`.
- [x] Python selects the changed functions and methods, including decorated ones, and refuses a non-importable path with a named reason → `test_python_changes_select_the_functions_and_methods_that_hold_them`.
- [x] Text and exception-message mutants are not reported; operator mutants and other exception arguments, such as an HTTP status, are → `test_text_only_python_mutants_are_not_reported`.
- [x] Route files with brackets or parentheses, such as `app/(shop)/[...slug]/route.ts`, are matched literally by Stryker's mutate patterns → `test_stryker_patterns_match_route_files_literally`.
- [x] Only checked mutants of changed functions count → `test_mutmut_statuses_count_only_checked_mutants_of_changed_functions`.
- [x] Stryker and mutation_test reports list each survivor with its mutated line → `test_stryker_and_mutation_test_reports_list_what_survived`.
- [x] A tool error or the time limit prints its reason and returns 0 → `test_mutation_report_never_fails_when_a_tool_errors_or_hits_the_limit`.
- [x] Cancelling the push stops the tool's processes, not only the mutation command → `test_interrupted_mutation_stops_the_tool_it_started`.
- [x] A filtered survivor does not hide the next one → `test_each_python_survivor_is_read_from_its_own_diff`.
- [x] A failed mutmut run reports its error instead of a clean result → `test_failed_mutmut_run_is_reported_instead_of_a_clean_result`.
- [x] Real mutmut lists the boundary survivor on the changed line and nothing from the unchanged method → `test_python_mutation_reports_real_survivors_on_changed_lines`.
- [x] Pre-push passes `--seconds 180 --in-place`, keeps the push when mutation fails, and leaves mutation time out of the budget warning → `test_pre_push_keeps_the_passed_push_over_budget_or_after_mutation_fails`.
- [x] Leftover mutation temporary directories are swept → `test_update_sweeps_day_old_hard_eng_temporary_directories`.

## Baseline + execution

Result: Passed
Evidence: main `9d041fc7` passed the Hard Eng workflow on push (run 36637175748).
Execution: One builder on branch `updater-and-mutation-followups`; the three tools were prototyped on fixtures first.

## Risks + recovery

Each push can take up to 180 seconds longer. mutation_test edits source in place, so it runs only in the pre-push snapshot or the command's snapshot. Tools install at their latest versions, so a changed report format shows as "could not run" until the parser is fixed, and the real mutmut test catches that for Python. Recovery is reverting the commit.

## ux_reference

N/A — terminal report text; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (1161 tests, 89.89% line coverage). On git fixtures with a boundary change on one line: Stryker 10.0.0 listed 2 of 6 mutants surviving (also as a pnpm workspace member, and for `src/[id]/route.ts` and `src/(group)/[...slug]/route.ts`), mutmut 3.8.0 2 of 5, mutation_test 1.8.1 2 of 9, and a Flutter package's single mutant was caught in 5.4s. A 2-second limit stopped Stryker, left no runner processes and exited 0. On this repository the report said mutmut cannot import `.hooks/hard-eng.py`.
E2E: Passed — the fixture runs above used the real tools through `hard-eng.py mutation --in-place`. On this repository, `hard-eng.py mutation --base origin/main` checked a snapshot of HEAD (all gates passed), printed the mutmut import reason, exited 0 and removed the snapshot in 108s.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
