# Fix the faults that the round 5 audit reproduced in normal use: gates that fail without a finding, debt that fails after a fix, errors that name no file, and start-up work that Stop does not use

Status: Ready

## Outcome + scope

A failed gate says what it found and where. A project that pays down recorded findings passes. An error in a project file names the file. A message that sends a person to a next step names a step that works. One Stop with nothing changed does less work than before round 4. Each item was reproduced by a round 5 audit run in a sealed copy, or by the coordinator.

Non-goals:

- Hook launcher faults, as one plan of their own for the next round. A push from a branch that has no Hard Eng files prints a raw Python error; an audit run reached it by normal steps (install on a branch, then push another branch). lefthook renames the pre-push launcher when `lefthook.yml` changes, and pushes then pass unchecked until the next session start. A second `pre-commit install` gives a false "pushes unchecked" note. Each fix changes a launcher text or where the launcher lives, and `is_own` in `.hooks/hook_chain.py` knows an own launcher only by its exact text. That plan starts with old-text recognition.
- The gates of a Poetry project. An audit run showed that its tests gate cannot import the project, and that Poetry takes the check's own throwaway environment for the project's. An investigation of the right command form runs beside this round. Its fix joins this plan only when a real Poetry run proves it; else it is the first item of the next round.
- Rare cases that no run reached in normal use: a worktree whose submodule cannot be fetched, two in-process builds of one release, a hand-made Husky layout with no post-checkout shim, a recorded release that the source no longer holds, a linked and ignored `.husky/_` in cleanup, an SSH host alias as `origin`, `adopt` that records an Import Linter error line, two wrong shapes of the gates file that print raw Python text, the wait hook with `sleep "$DELAY"` in a loop or `sleep infinity`, `hot-paths` with a missing path, the `Gap:` line for a repository that holds only shell or Docker files, and a no-remote project that needs a plan for a stage check asked for by name.
- Choices for the maintainer: whether Stop runs the workflow and shell checks, whether `ready` accepts the `unstable` merge state, the review bypass under classic "up to date" protection, a `ci_seconds` budget that the workflow time limit rounds up, a push straight to `main` in the source repository, a stale `finish` that still pushes memory, whether a tool configuration file at a JavaScript package root is production code, a one-word change of a test's expected value that counts as a big change, a failing plain Dart test that names no file, and Fallow, React Doctor, Dart Decimate and Trivy findings that cannot become adoption debt.
- The wait instruction for a worker with a long run. The coordinator's run reference and the subagents rule of the source repository word it in two ways. An auditor read it and ran nothing.
- `check` with no network. The tool lookup fails with the raw command error. No audit run reached it.
- The cost of the file scans at session start (about 60 ms on 2,000 files). This round's speed slice takes the Stop start-up only.

## Repository context

Owners: `scanner_result` and `FINDING_READERS` in `.hooks/reports.py` own what a failed scanner gate prints; `finding_lines` and `validate_fallow` in `.hooks/fallow_report.py` own the Fallow lines and its error. `fingerprints`, `neutral`, `by_form`, `judge` and `load` in `.hooks/debt.py` own debt lines, and `ANSI` there owns the pattern for terminal codes. `failure_summary` in `.hooks/agent_hooks.py` owns the Stop text of a failed check. `parse_config` in `.hooks/gate_config.py` owns the read of the gates file; six callers pass it that file's text. The gate result line in `.hooks/hard-eng.py` and `parallel_hint` in `.hooks/reports.py` own what a finished gate prints; `STOPPED` in `.hooks/process_group.py` records a stop. `python` and `summary` in `.hooks/mutation.py` own the mutation result. `placed_by_hard_eng` and `unchanged_checkout` in `.hooks/ship_actions.py` own the cleanup guard. The gate adapt loop in `.hooks/project_setup.py`, with `python_gate_command` and `python_roots` in `.hooks/python_setup.py`, owns the Python gate commands that setup writes. `require_listed_sources` in `.hooks/coverage_sources.py` owns the sources guard, `line_coverage` in `.hooks/reports.py` the coverage message, and the TypeScript sources check in `.hooks/untrusted_input.py` its error. The coordinator skill's host reference owns the route for a missing Trello key. `.hooks/update.py`, `.hooks/plans.py` and `.hooks/agent_hooks.py` own the modules and patterns that a Stop loads. The evidence is the six reports of the round 5 audit, which sit outside the repository. Each auditor worked in a sealed copy with no remote and stand-in programs for the outside services.
Same cause: eight causes. (1) A scanner report is read only when the gate passed. `features/osv-failure-findings` made OSV print on a failure (helped), and `features/audit-round-four` added readers for React Doctor, Fallow and the secret scan (helped for those three). Round 5 runs with a real finding showed five more types that fail without a finding: Semgrep, Trivy, Dart Decimate, jscpd and Import Linter. Fixing them one at a time has now left gaps two times, so this round closes the class: one test walks every report type in `SCANNERS`, and each type must have a reader or a stated reason that its tool prints its own findings. The Fallow reader also kept only items with a `path` of their own; unlisted dependencies, unlisted binaries and import cycles keep their place in a list. (2) A stored debt line is compared word for word. `fingerprints` makes digits and the checkout path neutral, and round 4 made the count word neutral (helped). Two more parts of a line change with no new finding: the unit of a time (Biome prints "2ms" in one run and "1548µs" in the next), and the source lines of a code frame, which change when a finding beside them is fixed. A search of the three readers of debt lines (`judge`, `record`, `require_shrink`) found that all compare through `by_form`, so that one function is the place. (3) A message drops the file, the reason or the next step. Rounds 1 to 4 fixed such messages one at a time (helped each time). This round takes each one that an audit run reached: a syntax error in a project file, the Stop text after a partial debt fix, the mutation result with no mutant, a stopped check, the TypeScript sources error, the Dart boundary error, the Dart sources and coverage messages and the Fallow workspace note. For the syntax error the search is complete: every read of a project file that a person edits goes through one helper that names the file. (4) Setup takes a gate command from the template and does not fit it to the project layout. `python_gate_command` wraps the command for the package manager, and the pytest path setting maps `src` to an import root (both helped). The dependencies gate still scans `.` with no first-party hint, so a `src` layout package that imports itself fails. A search of the Python template found three commands that setup adapts: pytest, deptry and Import Linter; pytest and Import Linter already read the layout. (5) A pattern covers one written form of a thing. `ANSI` strips colour codes and not link codes. The sources guard compares an entry as text, so `src/` and `./src` are not `src`. No earlier fix. A search of `.hooks/` for other readers of `sources` found that the others join each entry to the package folder, which accepts both forms. (6) The cleanup guard counts what Hard Eng itself made as the task's work. Round 4 took out the links and the copied hooks folder (helped). The compiled modules that Python writes beside the hooks when a hook runs are still counted, in each worktree where a hook ran. (7) A skill text names a step that its script refuses: the host reference tells a person to write the secrets file by hand, and the script refuses a secrets file that Git does not ignore. Only `save-secret` adds the ignore entry. No earlier fix. (8) A Stop with nothing changed loads modules and compiles patterns that it does not use. Round 4 timed Stop and kept it equal by the clock; an exact count showed 266 more Python calls in one Stop. No earlier fix of the start-up work itself.
Single source: `FINDING_READERS` alone decides which report types print findings on a failure, and its test reads `SCANNERS` for the full list. The neutral form of a debt line keeps one owner in `.hooks/debt.py`. `ANSI` in `.hooks/debt.py` stays the one pattern for terminal codes. One helper owns "read a project file and name it on a syntax error"; `load_policy` in `.hooks/shipping.py` has its own copy of that message for the gates file and moves to the helper. One function lists the children of a Python package's `src/` folder; `python_roots` and the dependencies gate both read it.
Escaped bug: every item is on the base branch and passed each gate on its PR. The test gate should have caught each one. Each gets a case that fails on `develop` before its fix. The items that change only wording or reference text have no new test and say why in their acceptance lines.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn.
Decided (1): a failed Semgrep, Trivy, Dart Decimate, jscpd or Import Linter gate prints its findings from its report, in the format of round 4: each line starts with the gate name and gives the place as `file:line`, at most 20 lines, and a last line counts the rest and names the report file. Semgrep gives rule, place and message. Trivy gives ID, title and place. Dart Decimate gives rule, place and message. jscpd names each copy by file and lines, never the code. Import Linter gives the lines of its "Broken contracts" part, or its error line when it finds no package. The readers in `.hooks/debt.py` for Semgrep and jscpd are not reused: they hold source text and no line number. Each reader is written against a real report of its tool.
Decided (2): a Fallow item with no `path` of its own takes its place from its first `imported_from` or `used_in` entry, or from its `files`. A workspace note that fails the gate is named in the error by its kind and message.
Decided (3): a time with a unit is one neutral token when two debt lines are compared, like the count word of round 4. The change is in the compare, not in the stored line, so a debt file from today's code passes with no new `adopt` run.
Decided (4): the source lines of a code frame are not debt lines. A frame line is a line that, in its neutral form, holds only an optional `>`, line numbers and spaces before a `│` or `|` bar. The compare leaves them out on both sides, so an old debt file passes, and the next `adopt` drops them from the file. After one of two findings is fixed, `check` then reports recorded lines as fixed and names `adopt`, as designed. This settles the item "debt lines that hold source context" from the round 4 list of choices: an audit run reached it by fixing one finding, and `adopt` could not clear it. Cost: a finding swapped for another of the same rule in the same file keeps the count and passes.
Decided (5): Stop shows the "recorded lines are fixed; run adopt" line of the gate whose output it shows. That line names its package, like the "findings beyond" line. The Stop heading names each failed gate with its package when the project has more than one.
Decided (6): a syntax error in a project file that a person edits gives one line that names the file by its path in the repository, the format and the parser's reason. It covers `hard-eng.gates.json`, a package's `package.json`, `hard-eng.debt.json`, `pubspec.yaml`, `l10n.yaml` and the agent settings files that setup reads. A debt file that holds a list gets the existing "must hold version 1" message. No read gives a traceback.
Decided (7): when the changed functions give mutmut nothing to change, the mutation report says "no mutants on the changed lines", which `summary` already prints for an empty result.
Decided (8): a gate that ends because the check was stopped prints that the check was stopped, with the signal where it is known, and no parallel tests hint.
Decided (9): the cleanup guard does not count `.hooks/__pycache__/`. Python writes it when a hook runs, and it never holds a person's work. The launchers keep writing compiled modules, because a hook with no compiled modules starts slower.
Decided (10): for a Python package whose import root is `src`, setup gives the dependencies gate one `--known-first-party` option for each package or module directly under `src/`. `python_roots` cannot give that list: it leaves out a package with no submodule, which is what a new library holds at install. A probe compared three forms in a `src` layout project with one script outside `src`: the scan root `src` missed a missing dependency in that script; the two roots `.` and `src` printed each finding in `src` two times; the option kept the scan and dropped only the false finding. A setup rerun adds the option to an existing dependencies gate that runs deptry with no first-party option, the way `strict_scanner_flags` already adds flags to an existing scanner gate.
Decided (11): the Dart sources message says to move the code under `lib/`. A hand run in the Flutter scaffold followed that step to a passing `check`. The second way, tests that import `package:test`, stays in the coverage message with its two conditions: `test` as a dev dependency, and a setup rerun that adds the VM test run. In today's Flutter scaffold the dev dependency does not resolve beside the pinned build tools, so the message names `lib/` first.
Decided (12): the TypeScript sources error names the files that the configuration omits and the configuration file. The JavaScript sources message also names the `include` list of that configuration.
Decided (13): a `sources` entry with a trailing slash or a leading `./` is read as the same folder.
Decided (14): on Claude Code and Codex the route for a missing Trello key or token is the route of the popup hosts: the person puts each value in a file and gives its path, and `save-secret` reads it. `save-secret` already makes Git ignore the secrets file. The script's refusal of a secrets file that Git does not ignore stays.
Decided (15): the speed slice changes only when code runs, not what it does: imports of the network modules move to the functions that use them, and a pattern that a Stop with nothing changed does not use is compiled at its first use. Two tests pin it: such a Stop loads no network module, and it starts no more Git commands than today.
Decided (16): `update-pr` and `update` with no update branch print no raw Git error line.

## Acceptance + steps

Slice 1, scanner findings:

- [ ] A failed Semgrep gate prints rule, place and message of each finding → `tests/test_scan_findings.py::test_a_failed_semgrep_gate_prints_rule_place_and_message`.
- [ ] A failed Trivy gate prints ID, title and place → `tests/test_scan_findings.py::test_a_failed_trivy_gate_prints_id_title_and_place`.
- [ ] A failed Dart Decimate gate prints rule, place and message → `tests/test_scan_findings.py::test_a_failed_dart_decimate_gate_prints_its_findings`.
- [ ] A failed jscpd gate names each copy by file and lines, never the code → `tests/test_scan_findings.py::test_a_failed_jscpd_gate_names_every_copy_without_its_code`.
- [ ] A failed Import Linter gate prints its broken contracts, or its error when it finds no package → `tests/test_scan_findings.py::test_a_failed_import_linter_gate_prints_its_broken_contracts`.
- [ ] A failed Fallow gate prints an unlisted dependency, an unlisted binary and an import cycle with their places → `tests/test_report_findings.py::test_a_failed_fallow_gate_prints_findings_that_have_no_path_of_their_own`.
- [ ] A Fallow workspace note that fails the gate is named by kind and message → `tests/test_report_findings.py::test_a_fallow_workspace_note_that_fails_the_gate_is_named`.
- [ ] Every report type has a reader of its findings or a stated reason that its tool prints them → `tests/test_scan_findings.py::test_every_report_type_shows_its_findings_on_a_failure`.

Slice 2, debt and Stop text:

- [ ] After one of two recorded findings is fixed, Stop shows the "recorded lines are fixed" line with the `adopt` step; the line names its package → `tests/test_stop_checks.py::test_stop_shows_the_adopt_step_when_recorded_lines_are_fixed`.
- [ ] A recorded line with a time in one unit equals the same line with another unit, and a debt file recorded by the base code passes → `tests/test_debt.py::test_a_time_in_another_unit_is_the_same_debt_line`.
- [ ] A changed source line in the code frame of a recorded finding is no new finding, for the real Biome and ruff frames; an old debt file with frame lines passes → `tests/test_debt.py::test_a_changed_source_line_in_a_code_frame_is_no_new_finding`.
- [ ] The Stop text holds no terminal link codes → `tests/test_stop_checks.py::test_stop_text_has_no_link_codes`.
- [ ] With two packages that fail, the Stop heading names each failed gate with its package → `tests/test_stop_checks.py::test_stop_names_the_package_of_each_failed_gate`.

Slice 3, project files that do not parse:

- [ ] A syntax error in `hard-eng.gates.json` names the file in `check` → `tests/test_project_files.py::test_a_gates_file_that_does_not_parse_is_named`.
- [ ] A syntax error in a package's `package.json` names that file with its package path → `tests/test_project_files.py::test_a_package_manifest_that_does_not_parse_is_named`.
- [ ] A syntax error in `hard-eng.debt.json` names the file, and a debt file that holds a list gets the version message → `tests/test_project_files.py::test_a_debt_file_that_does_not_parse_or_holds_a_list_is_named`.
- [ ] A `pubspec.yaml` with a syntax error gives one line that names it, with no traceback, in session start and `check` → `tests/test_project_files.py::test_a_pubspec_that_does_not_parse_is_named_without_a_traceback`.
- [ ] Setup names a broken `l10n.yaml` or agent settings file → `tests/test_project_files.py::test_setup_names_a_project_file_that_does_not_parse`.
- [ ] The Dart boundary error names the configuration file and the key to add → `tests/test_dart_config.py::test_the_missing_boundary_error_names_the_file_and_the_key`.

Slice 4, mutation, a stopped check, cleanup and update noise:

- [ ] Changed functions with no mutants give "no mutants on the changed lines" and no traceback → `tests/test_mutation.py::test_changed_functions_with_no_mutants_are_reported_as_no_mutants`.
- [ ] A stopped check says that it was stopped and prints no parallel tests hint → `tests/test_check_signals.py::test_a_stopped_check_says_that_it_was_stopped`.
- [ ] `ship --stage cleanup` removes a worktree that holds compiled hook modules → `tests/test_ship_cleanup.py::test_cleanup_does_not_count_compiled_hook_modules`.
- [ ] `update-pr` with no update branch prints no raw Git error → `tests/test_update_pr_refusal.py::test_update_pr_with_no_update_branch_prints_no_git_error`.

Slice 5, setup and source messages:

- [ ] A `src` layout package that imports itself passes the dependencies gate that setup writes, with the real deptry; a missing dependency outside `src` still fails → `tests/test_greenfield.py::test_a_src_layout_package_that_imports_itself_passes_the_dependencies_gate`.
- [ ] The Dart sources message names `lib/` as the step, and the guard passes after the move → `tests/test_greenfield.py::test_the_dart_sources_message_gives_a_step_that_passes`.
- [ ] The coverage message for Dart outside `lib/` names the move first and the two conditions of the second way → N/A — wording; the Reader check goes in Verification, and `tests/test_dart_coverage.py` still runs the refusal.
- [ ] The TypeScript sources error names the omitted files and the configuration file; with the folder in `include`, the check passes → `tests/test_typescript_sources.py::test_the_typescript_sources_error_names_the_files_and_the_configuration`.
- [ ] A `sources` entry written as `src/` or `./src` passes the guard → `tests/test_greenfield.py::test_javascript_and_dart_code_added_after_setup_must_join_the_checked_sources`, and `tests/test_greenfield.py::test_python_code_added_after_setup_must_join_the_checked_sources` for Python.

Slice 6, Trello key route (by the coordinator):

- [ ] The Claude Code and Codex route for a missing key or token ends in `save-secret` and a passing `probe` → N/A — skill text; the Reader check goes in Verification, and `tests/test_trello_coordinator.py` still pins the refusal of a file that Git does not ignore.

Slice 7, Stop start-up (after the join):

- [ ] A Stop with nothing changed loads no network module → `tests/test_gate_speed.py::test_stop_with_nothing_changed_loads_no_network_module`.
- [ ] A Stop with nothing changed starts no more Git commands than the base → `tests/test_gate_speed.py::test_stop_with_nothing_changed_starts_no_more_git_commands_than_before`.
- [ ] One Stop with nothing changed in the no-package fixture makes fewer than 103,551 Python calls, the count of the code before round 4 → N/A — a count from a tracing run outside the repository; the number goes in Verification.

Steps:

1. Each builder takes its slice in its own worktree.
2. For each item, the builder first writes the test and sees it fail on `develop` for the audit's reason. A test of a printed line uses the line that the real code or the real tool prints, never a line typed by hand. The builder's focused run holds the tests of each caller of a function that it changes, and the complexity command. A builder who reads a tool's report first makes a real report with that tool.
3. A test of a message that names a next step follows that step and sees it pass.
4. A builder who needs a line in a file or function that another slice owns stops and asks the coordinator.
5. The coordinator joins slices 1 to 6 and runs the full check once, directly after the join and before the reviews. Slice 7 starts on the joined branch.
6. After slice 7, the coordinator times session start and Stop, old against new, counts the Git commands that each Stop path starts, and counts the Python calls of one Stop. No auditor or builder runs during the timing.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 1ada0528, the merge of round 4. On that commit the `hard-eng` and `canary` CI checks passed on 2026-11-10. `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch, with this plan as the only change: exit 0. It reused the passed CI checks of that commit and ran the secret scan, which passed.
Execution: one builder on Sonnet for each of slices 1 to 5, each in its own worktree; the coordinator does slice 6; one builder does slice 7 on the joined branch. A fresh Opus reviewer reads the joined diff, and a second one reads the tests. A reader who did not write the texts runs the Reader check. Files have a limit of 1,000 lines. `.hooks/agent_hooks.py` is at 999, `.hooks/plans.py` at 998, `.hooks/hard-eng.py` at 996, `setup.py` at 995, `.hooks/gate_config.py` at 993, `.hooks/project_setup.py` at 981, `.hooks/reports.py` at 962 and `.hooks/update.py` at 949; `tests/test_reports.py` is at 984 and `tests/test_agent_hooks.py` at 951. Room by slice: slice 1 puts the new readers in a new module and adds at most 25 lines to `.hooks/reports.py`. Slice 2 changes `failure_summary` with no new line in `.hooks/agent_hooks.py`. Slice 3 puts the helper in a module with room and adds at most 5 lines to `.hooks/gate_config.py`, 4 to `setup.py` and 6 to `.hooks/project_setup.py`. Slice 4 adds at most 3 lines to `.hooks/hard-eng.py`; the words of a stopped gate live in `.hooks/process_group.py`. Slice 5 adds at most 8 lines to `.hooks/project_setup.py` and 3 to `.hooks/reports.py`. Slice 7 adds no line to `.hooks/agent_hooks.py` or `.hooks/plans.py`. A builder who needs more room moves code to the owner module that has room first.

- Slice 1: `scanner_result` and `FINDING_READERS` in `.hooks/reports.py`, `.hooks/fallow_report.py`, `.hooks/scan_findings.py` (new), `tests/test_scan_findings.py` (new), `tests/test_report_findings.py`.
- Slice 2: `.hooks/debt.py` without `load`, `failure_summary` in `.hooks/agent_hooks.py`, `tests/test_debt.py`, `tests/test_stop_checks.py`.
- Slice 3: `parse_config`, the `package.json` read and the Dart boundary check in `.hooks/gate_config.py`, `load` in `.hooks/debt.py`, `load_policy` in `.hooks/shipping.py`, the `pubspec.yaml` reads in `.hooks/project_setup.py` and `.hooks/swift_setup.py`, the `l10n.yaml` and settings reads in `setup.py` and its helpers, `tests/test_project_files.py` (new), `tests/test_dart_config.py`.
- Slice 4: `.hooks/mutation.py`, the gate result line in `.hooks/hard-eng.py`, `.hooks/process_group.py`, `.hooks/ship_actions.py`, `.hooks/update_pr.py`, `.hooks/update_runner.py`, `tests/test_mutation.py`, `tests/test_check_signals.py`, `tests/test_ship_cleanup.py`, `tests/test_update_pr_refusal.py`.
- Slice 5: the gate adapt loop in `.hooks/project_setup.py`, `.hooks/python_setup.py`, `.hooks/coverage_sources.py`, the coverage message in `line_coverage` in `.hooks/reports.py`, `.hooks/untrusted_input.py`, `tests/test_greenfield.py`, `tests/test_typescript_sources.py` (new).
- Slice 6: the coordinator skill's host reference.
- Slice 7: `.hooks/update.py`, `.hooks/plans.py`, `.hooks/agent_hooks.py`, `tests/test_gate_speed.py`.

Dependencies: slices 1 to 6 have none between them; no two share a function. Slices 1 and 5 edit `.hooks/reports.py` in different functions, slices 2 and 3 edit `.hooks/debt.py` in different functions, and slices 3 and 5 edit `.hooks/project_setup.py` in different functions. Slice 7 needs the join of slices 1 to 6.

## Risks + recovery

- A debt file loses its frame lines at the next `adopt`. Until then it passes as it is. A project needs no step.
- A finding swapped for another of the same rule in the same file passes the debt check, because the count per line form stays (Decided 4).
- A setup rerun adds the first-party option to the dependencies gate of a `src` layout package. A gate that already has that option, or that does not run deptry, stays.
- A project whose gate output held a time unit in a debt line passes where it failed at random. No project turns red from Decided (3) or (4): both only make more lines equal.
- The syntax error helper changes the words of an error that scripts may read. The parser's own reason stays in the line.
- A stopped gate prints a new line form. The Stop summary reads only "FAIL name (exit N" lines with a positive exit code, so a stopped gate was not in its list before and is not after.
- Uncertainty: a reader written from one real report can miss a shape that another version of the tool writes. Cheapest check: each reader returns no line for a shape that it does not know, and the gate still fails with its exit code, as today.
- Uncertainty: moving an import can slow the path that uses it by the import time. Cheapest check: the timing of step 6 on the update path.
- Recovery for any slice: revert its commit.

## ux_reference

N/A — hook, command and message changes with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey changes; each behavior is a hook, command or setup result that its test runs directly.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` and `canary` CI checks green. The PR holds the result of the independent review. Then the release into `main`.
