# Fix the faults that the round 6 audit reproduced in normal use: steps that cannot be done, checks that pass or fail wrongly, and failures that name no place

Status: Ready

## Outcome + scope

A step that a message names can be done in the checkout where the message appears. A check gives the same plan result with and without `--base`. The first Stop in a new checkout does not fail for a missing install. A failure names the file and the line that a person must open. Each item was reproduced by a round 6 audit run or by a real run of the coordinator, on `develop` 4ac88beb.

The bar for this round: build a fix for a wrong pass, a wrong fail, or a step that cannot be done. Fix minor wording only where its owner file is open for another fix.

Non-goals:

- Choices for the maintainer, not built: the dead-code gate fails dataclass fields that are read only through `dataclasses.asdict`, and a read by name passes; a tool configuration file at a JavaScript package root counts as production code; the Dart dead-code gate has no entry point, so each file under `lib/` counts as reachable; the Dart performance gate needs no time budget; an untracked file from before the session makes the change big, and the size line names the file; a test tsconfig that the root tsconfig does not reference is not type checked; debt can be added only by the change that installs Hard Eng; in a new Flutter app the "leave it in place" way of the Dart sources message cannot be done, because `test` does not resolve beside the pinned tools (round 5 kept that way on purpose).
- Outside cause: Bun passes a frozen install when the added version is already in `bun.lock` as an indirect dependency.
- A Python project with a `test/` folder gets gates that name `tests`. A rename of the folder passes each gate.
- Rare cases that no run reached in normal use: `ship` hides why a plan failed (pre-push stops such a plan first); the Stop hook inside a submodule or outside Git; wrong types typed by hand into the gates file; a path dependency missing from `depends_on`; a Trello write with no claim holder; a repository that merges with merge commits and keeps the old update branch.
- Minor items whose owner file this round does not open: the first `update-pr` prints one Git error line and then succeeds; captured `update-pr` output is out of order; "already differs; ask before replacing it" names no way; a setup rerun lists each installed path as not committed; a broken `l10n.yaml` fails under the lockfile gate with Flutter's own text; `check --related-tests` with no `--base` runs each test; the wording of one Stop line after an ADR block; the strict settings refusal of the Dart analysis options names no setting.
- A `for` loop with `sleep` passes the poll hook. A test allows a `for` retry on purpose.
- Hook launcher faults, the remaining direct parser reads, and a stale first-party name after a package is removed: carried from round 5, unchanged.

## Repository context

Owners: `validate_plans` in `.hooks/plans.py` owns when a plan is needed, with `size_verdict` in `.hooks/change_size.py`. `run`, `cleanup_guard` and `unchanged_checkout` in `.hooks/ship_actions.py` and `_clean` in `.hooks/shipping.py` own the ship refusals. `check` in `.hooks/hard-eng.py`, `quick_groups` in `.hooks/reports.py` and `check_lock_file` in `.hooks/process_group.py` own what a quick check runs. `line_coverage` in `.hooks/reports.py` owns the coverage numbers. `fingerprints`, `judge`, `record` and `settled_run` in `.hooks/debt.py` own debt lines and `adopt`. `repeat_note` in `.hooks/failures.py` owns the repeat count, and `failure_summary` in `.hooks/agent_hooks.py` owns the Stop text. `prepare_update` in `.hooks/update_runner.py` and `repair_current_hook` in `.hooks/update.py` own what a setup rerun does to the current checkout. The plan step of `setup.py` owns the gates file, and `merge` there owns the agent settings files. `merge_local_edits` in `.hooks/local_edits.py` owns the merge of local skill edits. `validate_package_services` and `validate_manifest_groups` in `.hooks/gate_config.py` and `validate_dart_boundaries` in `.hooks/dart_boundaries.py` own the check-time rules of a package, with `has_recursive_import_contract` in `.hooks/python_setup.py`. `jscpd_findings` in `.hooks/scan_findings.py` owns the copied-code lines. `dependency_command` and `validate_dart_exclusions` in `.hooks/project_setup.py` own the lock file and the analysis options rules. `.hooks/untrusted_input.py` owns the TypeScript configuration messages.
Same cause: seven causes. (1) A message names a step that nobody ran in the checkout where the message appears. Round 4 and round 5 fixed such messages one at a time (helped for those messages); round 5 added "a setup rerun" to two messages and proved the rerun with a direct `setup.py` run, which an installed project never uses (confounded: the proof ran another path). A real rerun on a task branch of an installed project changed nothing in the checkout: `setup.sh` sends an installed project to the update path, which plans from the remote base. Search: `command grep -rn -i "rerun setup\|setup rerun\|rerun the Hard Eng installer" .hooks setup.py` gives 18 lines. Five appear at check time on a task branch and need the gates file of the checkout: the two Swift group messages, the two Dart sources messages and the shell scripts message. The missing package message in `validate_manifest_groups` is of the same kind and names no step today. One more check-time line needs a tsconfig edit, not the gates file: it gets a hand step. The other twelve appear during setup or an update, or name the hook restore, and the base-branch path serves them. Other steps of this cause in this round: the two cleanup steps, the Draft plan line, and the Trello merge step that loops. (2) A plan-stage rule reads its scope from `HEAD` when no base is given, while the size rule reads the whole branch. One place: `validate_plans`. `validate_comments`, `validate_suppressions` and `require_shrink` take the same base; `require_shrink` already falls back to the branch point, and the other two check only changed lines, so they keep their scope. (3) A quick check leaves out the install gate, and no state says that this checkout has its installs. Reproduced for Python, JavaScript and Dart. One place: `quick_groups`. (4) A report is printed in the tool's own form of a path. Round 5 added the jscpd reader with the names as the report gives them (hurt: the names are relative to each scanned folder). Search: the other readers in `.hooks/scan_findings.py` and `FINDING_READERS` take paths that the tool gives from the package folder or as absolute paths; the round 5 tests for Semgrep, Trivy, Dart Decimate and Import Linter each ran the real tool in a package below the root or name why not. Only jscpd scans more than one folder. The debt reader of the same report in `.hooks/debt.py` keeps the names as the report gives them, because recorded lines hold that form. (5) A debt line is stored in a masked form, and the same masked form is printed for a new finding. One place: `judge`. (6) `adopt` and `check` apply the debt rule at different times. One place: `settled_run` gets the check that `require_shrink` makes. (7) An existing section stops a rule from reading it: `import_configuration` returns at an existing `[tool.importlinter]` table and `validate_package_services` asks only for the gate. Search: `has_recursive_import_contract` is called only for `setup.cfg` and `.importlinter`.
Single source: `default_branch_point` in `.hooks/plans.py` stays the one owner of the branch point; the new scope rule calls it. The install-versus-debt rule keeps one owner in `.hooks/debt.py`, called by `require_shrink` and by `settled_run`. `has_recursive_import_contract` becomes the one reader of an import contract for the three files that can hold it. The lockfiles gate stays the one install command of a package; the quick check runs that gate and holds no second copy of an install command. The "rerun setup" step keeps one command, `SETUP_COMMAND` in `.hooks/hook_chain.py`. Searched for copies: `command grep -rn "merge-base\|known-first-party\|--frozen-lockfile\|uv sync" .hooks setup.py`; no copy is added. The Dart Decimate settings file names had two copies after slice 5 (`setup.py` and the boundary rule); `SETTINGS_FILES` in `.hooks/dart_boundaries.py` is now the one list, and setup reads it.
Escaped bug: every item is on the base branch and passed each gate on its PR. The test gate should have caught each one. Each gets a case that fails on `develop` before its fix. Two items are faults of round 5 code: the jscpd names, and the "setup rerun" step of the two Dart sources messages. Their round 5 tests used a path that a project does not use (one scanned folder; a direct `setup.py` run). Their new tests use two scanned folders and the installed rerun path.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn.
Decided (1): with no `--base`, a clean tree and no applicable plan, `check` asks the size rule about the whole branch. A big branch with no plan fails with the size line, as pre-push does. A branch with no change prints no size line. The set of changed files that the other plan rules read stays as it is.
Decided (2): with `--plan-stage` and no plan, a change that the size rule calls small passes and prints the size line. A big change still fails.
Decided (3): a Draft plan with code edits gets a line that names the step: get approval, set the plan Ready, then build.
Decided (4): `ship --stage cleanup` with no `--worktree` stops first and names the option. The cleanup refusal for kept files names each top-level path once (no file count: Git lists an ignored folder as one entry) and names the step: remove the generated files that nobody needs, keep the rest, then run cleanup again. The clean checkout refusal names the first files.
Decided (5): the first quick check in a checkout runs the lockfiles gate of each package that it checks, one time. A file beside the check lock, in the Git folder of the checkout, lists the packages whose lockfiles gate passed there. A full check writes it too. A quick check of a package in that list runs the same gates as today. The first Stop in a new checkout takes the install time; today it fails wrongly and the agent must run a full check.
Decided (6): a coverage failure names up to five files with the most uncovered lines, with the count for each, for the Python, JavaScript and Dart coverage kinds.
Decided (7): a new finding beyond the debt prints the real output line. When the same masked line is also recorded, the message prints each real line of that form and says how many are new. The stored form does not change, so a debt file from today's code passes.
Decided (8): `adopt` refuses before it runs the gates when the branch point holds the install and no debt file, with the reason that `check` gives. With a debt file, `adopt` says how many current findings it did not record and that `check` fails on them.
Decided (9): a failed Stop counts as a repeat only when the checkout changed after the last count of the same failure.
Decided (10): the Stop text keeps the `DEBT` line of a gate when it shows the `FAIL` line of the same gate.
Decided (11): a setup rerun in an installed project also plans at the installed revision for the current checkout. When the planned `hard-eng.gates.json` differs, the rerun writes it to the working tree, does not commit it, and names it in its result. It does so on a task branch and in a project with no remote. It also writes each planned project file that the checkout does not have yet, for example the `tsconfig.json` of a new package: the joined proof showed that a new JavaScript package got its group and then failed the types gate with a raw command error, because that file was missing. It replaces no other existing file and no scaffold file; those stay with the update path. When setup refuses the plan for the checkout, the result names the reason and the update goes on, as before this round; with a missing pre-push hook the rerun still stops. The same holds when the installed release cannot be fetched: the joined proof showed a raw Git error in a project with no remote, where the old code printed the "pushed" line. `repair_checkout` now lives beside its caller in `.hooks/update_runner.py`, because `.hooks/update.py` was at the line limit. An update at session start does not touch the checkout.
Decided (12): when a package manifest of a supported language has no group, the setup plan adds its group from the template, as a first install does. The check message names the rerun.
Decided (13): the agent settings merge matches a Hard Eng hook entry by its command. The project's entry stays, with the project's timeout, and no second entry is added.
Decided (14): an update or a rerun that cannot reach the release host says which address failed and that the step is to try again with a network; a project with its install commit not yet on the base branch gets the "updates start after the project is pushed" line.
Decided (15): a local edit of a Trello skill line that conflicts with an update prints each conflict with the local lines and the update's lines, and says that the update's lines must replace the local lines before the next update.
Decided (16): `check` fails a Python package whose import root has no contract in the file that Import Linter reads, and prints the lines to add. This is a check-time rule; the setup plan does not get a new refusal, because a refusal there stops updates. It runs with the imports gate (`require_import_contract`, called by `prepare_command`), not at the config load, because each session start loads the config.
Decided (17): the copied-code lines name each file by its path from the repository root. The printing reader finds the gate of the report in the gates file and tries each name under each scanned folder of that gate. A name that exists under two scanned folders prints both paths with "or", because the report cannot tell them apart. The gate command does not change: the `--absolute` option of jscpd would give exact names, but the debt reader in `.hooks/debt.py` stores the names of the same report, so each recorded copied-code line of an installed project would stop matching, and debt can only shrink.
Decided (18): a failed read of the Dart Decimate settings prints the tool's own text. The values of a boundary rule are path prefixes: a prefix that matches no Dart file of the package fails and names the prefix.
Decided (19): a rule set to `false` in the `linter: rules:` map of the analysis options is refused, as the other ways to switch a rule off are. The exclude refusal names the file and the entry.
Decided (20): setup refuses a lock file that Git ignores, for each language, and names the step: remove its ignore entry and commit the file. The rule runs at setup only, from the file list that setup already has, so no check gets a new Git start.
Decided (21): a `dart test` run that ends before its first test event prints the lines that the tool wrote in place of events.
Decided (22): the message for a TypeScript configuration that omits the declarations file names that configuration file and the entry to add to its `include` or `files` list. It names no rerun.
Decided (23): `generated_sources` in `.hooks/gate_config.py` asks Git for the attributes with one process. It asks whether the folder is in a repository only when that process fails. Found by the speed count of this round: one config load started four processes for that question, at each session start and at each Stop with a change. This also pays for the three module files that this round adds to `.hooks/`, because the config load reads each tracked file.

## Acceptance + steps

Slice 1, plans and ship (`.hooks/plans.py`, `.hooks/change_size.py`, `.hooks/ship_actions.py`, `.hooks/shipping.py`):

- [ ] `check` with no `--base` fails a committed big change with no plan and prints the size line; a branch with no change prints no size line → `tests/test_plans.py::test_a_check_with_no_base_judges_the_size_of_the_whole_branch`.
- [ ] `check --plan-stage Complete` passes a small change with no plan and prints the size line; a big one fails → `tests/test_plans.py::test_a_plan_stage_check_passes_a_small_change_with_no_plan`.
- [ ] A Draft plan with code edits gets a line that names approval and Ready → `tests/test_plans.py::test_a_draft_plan_with_code_edits_names_the_ready_step`.
- [ ] `ship --stage cleanup` with no `--worktree` names the option before any other refusal → `tests/test_ship_cleanup.py::test_cleanup_with_no_worktree_names_the_option`.
- [ ] The cleanup refusal names each kept top-level path once and the step → `tests/test_ship_cleanup.py::test_the_cleanup_refusal_names_every_kept_path_and_the_step`.
- [ ] The clean checkout refusal names the changed files → `tests/test_shipping.py::test_the_clean_checkout_refusal_names_the_files`.

Slice 2, check runner (`.hooks/hard-eng.py`, `.hooks/reports.py`, `.hooks/coverage_sources.py`, `.hooks/process_group.py`, `.hooks/dart_test_report.py`):

- [ ] The first quick check in a checkout runs the lockfiles gate of the checked package one time; the second quick check does not; a full check marks the package too → `tests/test_quick_check.py::test_the_first_quick_check_in_a_checkout_runs_the_install_one_time`.
- [ ] A coverage failure names the files with the most uncovered lines, for each coverage kind → `tests/test_reports.py::test_a_coverage_failure_names_the_least_covered_files`.
- [ ] A `dart test` run that ends before its first test event prints the tool's lines → `tests/test_dart_test_report.py::test_a_run_with_no_test_event_prints_the_reason`.

Slice 3, debt and Stop text (`.hooks/debt.py`, `.hooks/failures.py`, `.hooks/agent_hooks.py`):

- [ ] A new finding beyond the debt prints its real line and column; with a recorded line of the same form it prints the candidates and the count of new ones; a debt file from the base code passes → `tests/test_debt.py::test_a_new_finding_beyond_the_debt_prints_its_real_line`.
- [ ] `adopt` refuses before the gates run when the branch point holds the install and no debt file → `tests/test_debt.py::test_adopt_refuses_first_when_check_would_refuse_the_debt_file`.
- [ ] `adopt` with a debt file says how many findings it did not record → `tests/test_debt.py::test_adopt_says_how_many_new_findings_it_left_out`.
- [ ] A second failed Stop with no change in the checkout adds no repeat; a failed Stop after an edit does → `tests/test_failures.py::test_a_failure_with_no_change_between_stops_is_not_a_repeat`.
- [ ] The Stop text keeps the `DEBT` line of a gate whose `FAIL` line it shows → `tests/test_stop_checks.py::test_stop_keeps_the_debt_line_of_a_failed_gate`.

Slice 4, setup rerun and update (`.hooks/update.py`, `.hooks/update_runner.py`, `setup.py`, `.hooks/local_edits.py`, and two modules moved out of `setup.py` for the line limit: `.hooks/settings_merge.py`, `.hooks/legacy_command.py`):

- [ ] A setup rerun on a task branch of an installed project writes the planned gates file to the checkout and names it; with no remote it does the same → `tests/test_update_runner.py::test_a_rerun_writes_the_planned_gates_file_to_the_current_checkout`.
- [ ] A rerun writes the files that setup plans for a new package and that the checkout lacks, and no scaffold file → `tests/test_update_runner.py::test_a_rerun_writes_each_project_file_that_setup_plans_and_no_scaffold_file`.
- [ ] A rerun in a checkout that setup refuses names the reason, changes no file and still reports the update → `tests/test_update_runner.py::test_a_rerun_goes_on_when_setup_refuses_the_checkout`.
- [ ] A rerun in a project with no remote keeps the "pushed" line when the installed release cannot be fetched → `tests/test_update_runner.py::test_a_rerun_with_no_remote_keeps_the_pushed_line_when_the_fetch_fails`.
- [ ] A session-start update leaves the checkout as it is → `tests/test_update_runner.py::test_an_update_at_session_start_does_not_touch_the_checkout`.
- [ ] The setup plan adds the template group of a package whose language the gates file lacks, and keeps each existing group as it is → `tests/test_setup.py::test_the_plan_adds_the_group_of_a_new_package`.
- [ ] The settings merge keeps one hook entry when the project changed its timeout → `tests/test_hook_setup.py::test_a_changed_timeout_keeps_one_hook_entry`.
- [ ] A rerun with no network names the address and the step → `tests/test_updates.py::test_no_network_names_the_address_and_the_step`.
- [ ] A project whose install commit is not on the base branch gets the "pushed" line → `tests/test_update_runner.py::test_an_install_that_is_not_on_the_base_branch_gets_the_pushed_line`.
- [ ] A conflicting local edit prints each conflict with both texts and the step → `tests/test_updates.py::test_a_conflicting_local_edit_shows_both_texts_and_the_step`.

Slice 5, gate rules (`.hooks/gate_config.py`, `.hooks/python_setup.py`, `.hooks/dart_boundaries.py`):

- [ ] A rule set to `false` in the `linter: rules:` map is refused, and the refusal names the file and the rule → `tests/test_dart_config.py::test_a_linter_rule_set_to_false_is_refused_by_name`.

- [ ] `check` fails a Python package with an import root that the contract in `pyproject.toml` does not cover, and prints the lines to add; a covered root passes → `tests/test_greenfield.py::test_a_python_root_with_no_import_contract_fails_the_check`.
- [ ] A failed read of the Dart Decimate settings prints the tool's text → `tests/test_dart_config.py::test_a_settings_file_that_the_tool_rejects_shows_the_tools_text`.
- [ ] A boundary rule with a prefix that matches no Dart file fails and names the prefix; a prefix of a folder name that matches files passes → `tests/test_dart_config.py::test_a_boundary_rule_with_a_missing_folder_is_refused`.
- [ ] The missing package message names the setup rerun → `tests/test_package_discovery.py::test_a_package_with_no_group_names_the_rerun`.
- [ ] The Git attributes reader starts one Git process for a folder in a repository, and still returns no name for a folder outside one → `tests/test_dart_config.py::test_generated_sources_starts_one_git_process_in_a_repository`.

Slice 6, setup rules (`.hooks/project_setup.py`, `.hooks/scan_findings.py`, `.hooks/untrusted_input.py`):

- [ ] The copied-code lines name each file by its path from the repository root, for the two report entries that the real jscpd 5.4.3 wrote for two scanned folders with the same relative name; the same name in both folders prints both paths; with no gates file the names print as given → `tests/test_scan_findings.py::test_copied_code_lines_name_paths_from_the_repository_root`.
- [ ] The exclude refusal of the analysis options names the file and the entry → `tests/test_setup_rules.py::test_the_exclusion_refusal_names_the_file_and_the_entry`.
- [ ] Setup refuses a lock file that Git ignores and names the step; after the step the plan passes → `tests/test_setup_rules.py::test_an_ignored_lock_file_is_refused`.
- [ ] The declarations message names the TypeScript configuration file and the entry to add → `tests/test_untrusted_input.py::test_the_declarations_message_names_the_configuration_file`.

Joined proof, by the coordinator:

- [ ] Each "rerun setup" step that appears at check time is done in a real installed fixture on a task branch, and the check then passes: a new Swift group, a new language package, a new package under `src/`, and Dart code outside `lib/` with `test` as a dev dependency → N/A — a run with a real install from a local release host and the real tools, outside the repository; the result goes in Verification.
- [ ] Stop is not slower in a checkout that has its installs: the real hook commands, old against new, compiled modules, alternating runs, medians, with the counts of Git starts and Python calls → N/A — a timing run outside the repository; the numbers go in the Speed line of Verification.
- [ ] Reader check of each new or changed message, by a subagent that did not write it → N/A — a reading, not a test; the result goes in Verification.
- [ ] `python3 .hooks/hard-eng.py challenge` on the candidate commit, then the Complete check one time on the last commit → N/A — the two results go in Verification.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 4ac88beb, the merge of round 5. On that commit the `hard-eng` and `canary` CI checks passed on 2026-11-10. `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch, with this plan as the only change: exit 0.
Execution: one builder on Sonnet for each of slices 1 to 6, each in its own worktree, each with one failing test before each fix. No two slices write the same file. Six files are at or near the 1,000 line limit (`setup.py`, `.hooks/agent_hooks.py`, `.hooks/hard-eng.py`, `.hooks/gate_config.py`, `.hooks/plans.py`, `.hooks/reports.py`); each has one writer, and that writer frees the lines it adds. Each brief lists every static gate command. The coordinator joins the slices, runs the static gates and the focused tests, and does the joined proof. A fresh Opus reviewer reads the joined diff, and a second one reads the tests.

Dependencies: slices 1 to 6 have none between them. Slice 5 changes the missing package message to name the rerun that slice 4 makes work; the joined proof runs it.

## Risks + recovery

- A plain `check` on a branch with a committed big change and no plan now fails where it passed. Pre-push already fails that branch.
- The first Stop in a new checkout takes the install time. A checkout that ran any check before this change has no list yet, so its next quick check runs the install gates one more time; they are fast when the install is current.
- A rerun writes the gates file into the working tree. It writes only when the plan differs, and it leaves the commit to the person. Uncertainty: the plan step can refuse a checkout for a cause that the base branch does not have. Cheapest check: the refusal prints as the rerun's result and nothing is written, as today.
- The setup plan adds a group for a new package during an update too. A project whose check already fails with "missing from gate configuration" gets the group in its update PR.
- A project with a Python root that its contract does not cover now fails `check` with the lines to add. Its imports gate passed a cycle in that root before.
- A project whose lock file is ignored now fails setup, and so its next update. Its fresh clones failed before.
- A rule set to `false` in `linter: rules:` now fails. The step is to remove the entry.
- The printed copied-code lines change their form. The debt reader of the same report is unchanged, so recorded copied-code lines still match.
- Recovery for any slice: revert its commit.

## ux_reference

N/A — hook, command and message changes with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey changes; each behavior is a hook, command or setup result that its test runs directly, and the joined proof runs the rerun steps in a real installed fixture.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` and `canary` CI checks green. The PR holds the result of the independent review. Then the release into `main`.
