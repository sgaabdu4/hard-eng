# Fix the faults that the round 4 audit reproduced in normal use: dead ends as a project grows, messages that name no step or reason, and gates that live on after a stop

Status: Ready

## Outcome + scope

A project that grows after install no longer reaches a check that names no way out, and no longer gets a pass that checked nothing. A failed check, update or ship step says what failed and what to do next. A stopped check leaves no running gate. Each item was reproduced by a round 4 audit run in a sealed copy, or by the coordinator.

Non-goals:

- A raw Python error at push on a branch that has no Hard Eng files. The fix needs a new launcher text, and `is_own` in `.hooks/hook_chain.py` knows an own launcher only by its exact text. Old launchers would then count as project hooks. It needs old-text recognition first, as its own plan.
- A push snapshot that stays in the temporary folder after Ctrl-C. `sweep_temporary` in `.hooks/update_runner.py` already removes a left snapshot of the repository after 24 hours, in each background update. A second cleanup in the pre-push would copy that owner.
- A Dart or Flutter package that ignores `pubspec.lock`. Its lockfile gate passes locally and fails in each fresh checkout, with Dart's own clear reason. A setup refusal would also stop each update of a library package that follows Dart's advice.
- A second Python root package that a project adds after install. An existing Import Linter block in `pyproject.toml` does not name it, and the gate passes. The design review found it by a probe; no audit run reached it.
- A project with no `origin/<base>` ref, such as a new project before its first push. There the size count and the plan scope both read only the uncommitted work, so they agree. A stage check asked for by name then needs a plan for that work, as designed.
- A project with no shipping policy: session start still builds the update branch, and `update-pr` then stops at the missing policy. The message is true, and it now names the step.
- The 24 hour memory of a refused update. The message names the published setup command, and that command retries at once.
- `adopt` stopped by SIGTERM. A person runs it in a terminal, where Ctrl-C already stops its gates.
- Choices for the maintainer: debt lines that hold source context, Dart `example/` in coverage, the move to Bun for npm, pnpm and yarn projects, a deleted skill that an update brings back, one committed scaffold edit that blocks each update, a new review after a rebase, a review record with findings that passes ship, the coordinator lease time, a stricter wait rule for `for` loops, the basic mode pass line, the Dart dead-code entry point, the Swift file length rule, a `Gap:` line for a second language, the Trello title checks in `new` and `update --name`, and a two-day wait for the mise launcher.
- Rare cases that no run reached in normal use: a sign-in prompt through `GIT_ASKPASS` in a background update, a fix worktree left after a merged update, a workflow generated before 2026-09-10 that migrates into one that fails actionlint, a cut-off session state file, Python tests in `test/`, an instruction file inside an ignored `venv/` folder, the size reason after commits on a local default branch with no remote, submodule reuse from a local path, and a failing XCTest with no reason.
- A missing package script that fails only its own gate. The message now names the package, gate and script; the validation still stops the check, as it does for each wrong gate file.
- The mutation report wording for lines that no test runs.

## Repository context

Owners: `require_roles` and `validate_required_checks` in `.hooks/gate_config.py` own the mandatory roles, their message and the early return for a gates file with no package. `import_configuration` in `.hooks/python_setup.py` owns the Import Linter block. `unlisted_shell_scripts` in `.hooks/project_setup.py` and `configure_shellcheck` in `setup.py` own the shell script lists. `require_listed_python_sources` in `.hooks/python_setup.py` owns the sources guard. `publish` in `.hooks/update_pr.py`, and `ready_revision`, `update_base`, `published`, `locked_update` and `refuse_untracked_overlap` in `.hooks/update_runner.py`, own the update messages and the recorded result. `commit_install` in `.hooks/update.py` owns the install refusal. `_ready_state` and `_delivery` in `.hooks/shipping.py` own the ready and delivery refusals. `link_local_files` and `unchanged_checkout` in `.hooks/ship_actions.py` own the local links and the cleanup guard. `run_checks` in `.hooks/gate_schedule.py` owns the stop of gate groups, and `main` in `.hooks/hard-eng.py` owns the command entry. `scanner_result` in `.hooks/reports.py` owns what a failed scanner gate prints. `failure_summary` in `.hooks/dart_test_report.py` owns a Dart test failure line. `fingerprints`, `judge`, `record` and `require_shrink` in `.hooks/debt.py` own debt lines. `failure_summary`, `bounded` and `completion_notice` in `.hooks/agent_hooks.py` own the Stop text. `REQUIREMENT_ID`, `requirement_references`, `released_plans` and `report_stage` in `.hooks/plans.py` own the requirement IDs, the released plans and the stage line. The evidence is the six reports of the round 4 audit and one follow-up, which sit outside the repository. Each auditor worked in a sealed copy with no remote and stand-in programs for the outside services. The coordinator reproduced the imports dead end in a copy of a new Python project. A design reviewer then tried each decision against the code with probes; its changes are in the Decided lines.
Same cause: seven causes. (1) Setup plans the gates from the files at install, and nothing updates them when the project grows. The roles that a later file brings are imports, shell, workflows, ci-security, deployment, boundaries, react and the package script roles. Earlier fixes: `require_listed_python_sources` from `features/python-greenfield-setup` (helped for Python) and the listed shell script guard `require_listed_shell_scripts` (helped for a second script). Both name a step. A search of `.hooks/gate_config.py` found six `require_roles` calls and one inline copy of its message in the package role check. The role message is fixed once, at `require_roles`, for all of them. (2) A message drops the reason, the owner or the next step. Rounds 1 to 3 fixed such messages one at a time (helped each time): `features/audit-round-two`, `features/audit-round-three`, `features/osv-failure-findings` and `features/failed-gate-recap`. This round takes each one that an audit run reached. No search can list every such message, so the next audit reads the areas that this round did not reach. (3) A scanner report is read only when the gate passed. `features/osv-failure-findings` made the OSV report print on a failure (helped). `scanner_result` reads a report on a failure only for OSV. Audit runs showed three more gates whose failure prints no finding: React Doctor, Fallow and the secret scan. The other report types were not run with a finding in this round; the next audit runs them. (4) A stored line is compared word for word. `fingerprints` already makes digits and the checkout path neutral (helped). The count word still changes between one and many. Probes of 2026-11-10 ran each tool with one finding and with two. `ruff check` prints "Found 1 error." and "Found 2 errors.", and "1 hidden fix" and "2 hidden fixes". `ruff format` prints "1 file" and "2 files". Biome prints "Checked 1 file" and "Found 1 error.", and the plural for more. `dart analyze` prints "1 issue found." and "2 issues found.". tsc and vulture print no summary line when the output is not a terminal. The audit run showed the pyrefly line. The three readers of debt lines are `judge`, `record` and `require_shrink`. (5) A stop signal does not reach the code that cleans up. `features/process-group-timeouts` made a timeout stop the whole group (helped). `pre_push` and `mutate` in `.hooks/ship_actions.py` turn SIGTERM and SIGHUP into their cleanup (helped for those commands). A handler swap with a signal mask inside `run_in_group` was reverted by `features/revert-interrupt-start` (hurt: it left signals blocked in a test worker). A search of each `signal.signal` and `start_new_session` call in `.hooks/` found the Stop hook, the pre-push, the update worker and the gate groups. Of the commands that run gates, `check` and `adopt` have no handler. The update worker is meant to outlive its parent. (6) One pattern has two copies: `REQUIREMENT_ID` and the `git grep -E` text in `requirement_references`. No earlier fix. (7) A local ref is read as the released state: `released_plans` counts the local default branch tip when `origin/<base>` exists, and `ready_revision` does not read the local `origin/<base>`. `features/release-plan-scope` and `features/stale-update-branch` fixed nearby cases (helped). A search found two readers of `release_references`: `default_branch_point`, which takes the first ref that resolves and tries `origin/<base>` first, and `released_plans`, the only one that compares tips.
Single source: `REQUIREMENT_ID` alone decides what is a requirement ID; the `git grep` text in `requirement_references` becomes a loose first filter that names no ID format. The "code outside its sources" guard gets one owner for Python, JavaScript and Dart. The Import Linter block has one owner, `import_configuration`; the new failure text prints what that function builds. The neutral form of a debt line has one owner in `.hooks/debt.py`. `report_stage` owns the words of each stage line; `completion_notice` relays a stage line by its shape and holds no stage name. The "missing mandatory checks" message has one owner, `require_roles`; the inline copy in the package role check merges into it. "A project shell script" has one rule, used by the mandatory role test, `unlisted_shell_scripts` and `configure_shellcheck`. The pattern for terminal colour codes has one owner, `ANSI` in `.hooks/debt.py`. A search of `.hooks/`, `setup.py`, `new_project.py` and `release_canary.py` on 2026-11-10 found no other copy of the ID pattern, the Import Linter block or the stage lines.
Escaped bug: every item is on the base branch and passed each gate on its PR. The test gate should have caught each one. Each gets a case that fails on `develop` before its fix. The items that change only wording or reference text have no new test and say why in their acceptance lines.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn.
Decided (1): setup still writes no `imports` gate while no Python package has a module; `tests/test_setup.py::test_standalone_python_does_not_invent_import_architecture` pins that. When the first module comes, the "missing mandatory checks" message names the step (Decided 2). When an `imports` gate then fails and the package has no Import Linter configuration, the failure also prints the block to add, built by `import_configuration`. The hint is made only after a failure, so a passing gate pays nothing. A design that keeps the gate from the start was dropped: it needs a new pass in the runner, a change of the pinned test and a gate migration in setup.
Decided (2): the "missing mandatory checks" message names the next step for every role: add a gate for each role to that group in `hard-eng.gates.json`, from the language template for a package role or from the gates reference for a shared role. The gates reference gains the commands of the shared roles. A setup rerun is not named, because the published setup command builds from the remote base, which does not hold the new file yet.
Decided (3): Hard Eng's own hook launchers do not make the `shell` role mandatory, and setup does not list them in a new shell gate. The listed shell script check already leaves them out (`tests/test_deployment_and_shell_gates.py::test_own_hook_launcher_needs_no_shellcheck_entry`). A first install into a Husky project then loads with no shell gate, where it stopped before.
Decided (4): a gates file with no package and no supported manifest takes an early return in `validate_required_checks`. Basic mode projects and gates files with only ad-hoc groups take it. Before that return, the check now requires the roles that a file brings: `shell` for a project shell script, `workflows` and `ci-security` for a workflow, and `deployment` for a deployment file. It also runs the listed shell script check. A gate that names its tool and has no role field still counts, as today. The secret scan roles do not become mandatory there.
Decided (5): one sources guard covers Python, JavaScript and Dart. This reverses a round 3 non-goal: an audit run got "100%" line coverage with 4 of 46 lines hit in a new folder. An installed project with code outside its `sources` must list the folder or file; the message names it. A top-level tool configuration file added after install counts, as one present at install does. The guard ships as its own commit.
Decided (6): `HE-` IDs may have one part, so `HE-YAGNI` is checked. `REQ-` IDs keep two parts or more, so a ticket key such as `REQ-123` in a project's Markdown stays out of the check. A heading in a registry file that starts with `HE-` or `REQ-` and is not a valid ID is an error that names it. The requirements intro states the format.
Decided (7): a debt line and a current line are equal when the word after a count differs only in its ending for one or many: "error" and "errors", "fix" and "fixes". The neutral form drops a final "s", then a final "e", from that word. `judge` and the adopt shrink use it. The shrink keeps the recorded spelling of a line that is still there, so `require_shrink` sees no new line and the debt file keeps its format. No adopted project needs a new `adopt` run.
Decided (8): the `check` command turns SIGTERM and SIGHUP into the interrupt that already stops its gate groups. It sets the two handlers once, in the `check` branch of the command entry, as `pre_push` does in its own command. It swaps no handler back and masks no signal, which was the reverted design. A SIGHUP that the process got as ignored stays ignored, so a `nohup` run lives on. Its test runs `check` as its own process.
Decided (9): with `origin/<base>` present, the local default branch tip is not a release tip in `released_plans`. The size count already reads the branch from `origin/<base>`; the plan scope now reads the same commits. A plan in an unpushed commit on the default branch then covers a later fix. A task branch checked against a local default branch that is ahead of `origin/<base>` changes too: the unpushed plan covers it.
Decided (10): a passing quick check prints "Hard Eng: quick checks passed; tests run in the full check." where it printed the ready-for-ship line. The full check keeps its line. The Stop hook relays any stage line by its shape.
Decided (11): a failed React Doctor, Fallow or secret scan gate prints its findings from the report, at most 20: file, line where the report has one, rule and message. The secret scan never prints the secret; its test builds the fake token at run time.
Decided (12): `ship --stage ready` reads the required checks before it judges a state that is not clean, so a pending or failed check is the reason given.
Decided (13): the cleanup guard does not count what `link_local_files` put in a worktree: a link into the main checkout, and its copy of an ignored hooks folder. Any other ignored file still stops the cleanup.
Decided (14): `update-pr` exits 1 after a remembered refusal and does not print "Nothing to publish". The Stop note reads the local `origin/<base>` ref, with no network call, and says to pull or rebase when the update is already there. A setup rerun records its result in `locked_update` in `.hooks/update_runner.py`, so `setup.py` does not change for it.
Decided (15): new validation runs in the session start path only when a timing run shows no slower median. If a median grows, that check moves to `check` only.

## Acceptance + steps

Slice 1, updates:

- [ ] `update-pr` after a remembered refusal prints the refusal, exits 1 and does not say "Nothing to publish" → `tests/test_update_pr_refusal.py::test_update_pr_fails_after_a_remembered_refusal`.
- [ ] After the update is on the local `origin/<base>`, the Stop note says to pull or rebase and names no `update-pr` step → `tests/test_update_runner.py::test_the_note_says_pull_when_the_update_is_already_on_the_base`.
- [ ] A failed `git ls-remote` in an update gives Git's own last error line → `tests/test_update_runner.py::test_a_failed_remote_lookup_keeps_gits_reason`.
- [ ] With the update branch checked out in the main checkout, the refusal says to switch that checkout to another branch → `tests/test_update_runner.py::test_the_refusal_for_a_main_checkout_names_a_step_that_works`.
- [ ] The refusal for an untracked file in the way says to move it, and does not say to commit it → N/A — wording; the Reader check goes in Verification, and `tests/test_update_runner.py::test_an_update_refuses_a_local_file_where_it_needs_a_folder` still runs the refusal.
- [ ] An install over uncommitted work names only the paths that had local changes → `tests/test_updates.py::test_install_over_local_changes_names_only_the_changed_paths`.
- [ ] A setup rerun that builds the update records its result, so the next session start does not say the last update failed → `tests/test_update_runner.py::test_a_setup_rerun_records_its_result`.

Slice 2, shipping and stop signals:

- [ ] `ship --stage ready` on a PR that is not clean, with a required check pending or failed, gives the check as the reason → `tests/test_shipping.py::test_ready_names_a_pending_or_failed_check_before_the_review_state`.
- [ ] `ship --stage cleanup` removes a worktree that holds only what Hard Eng put there, and still refuses one with another ignored file → `tests/test_ship_cleanup.py::test_cleanup_ignores_only_what_hard_eng_put_in_the_worktree`.
- [ ] A failed delivery check prints the reason that its command gave → `tests/test_shipping.py::test_a_failed_delivery_check_keeps_its_reason`.
- [ ] A push with no shipping policy names the step that adds one → N/A — wording; the Reader check goes in Verification, and `tests/test_ship_actions.py::test_pre_push_rejects_missing_shipping_before_commands` still runs the refusal.
- [ ] `check` stopped by SIGTERM or SIGHUP stops its running gates → `tests/test_check_signals.py::test_a_stopped_check_stops_its_gates`.

Slice 3, gates and setup:

- [ ] An `imports` gate that fails in a package with no Import Linter configuration prints the block to add; with the printed block added, the real Import Linter passes → `tests/test_greenfield.py::test_an_imports_gate_without_a_contract_prints_the_block_to_add`.
- [ ] A missing mandatory check names the gates file, the templates and the gates reference as the next step, from one owner → N/A — wording; the Reader check goes in Verification, and `tests/test_freshness.py::test_groups_require_freshness_role` still runs the refusal.
- [ ] The gates reference lists the shared roles with their commands, inside its size limit → N/A — reference text; the Reader check goes in Verification, and `tests/test_skill_links.py` checks the size.
- [ ] A JavaScript package with a missing package script gets an error that names the package, the gate and the script → `tests/test_package_discovery.py::test_a_missing_package_script_names_package_gate_and_script`.
- [ ] A gates file with no package fails with the mandatory check message after a shell script or a workflow is added; a script left out of the shell gate is named → `tests/test_basic_mode.py::test_basic_mode_requires_checks_for_scripts_and_workflows_added_later`.
- [ ] After a first install into a Husky project with no shell script of its own, the gates file loads with no shell gate, and a setup rerun adds none; a project script added later still makes the role mandatory → `tests/test_husky_setup.py::test_own_launchers_alone_need_no_shell_gate`.
- [ ] The performance suite error names its package → `tests/test_greenfield.py::test_the_performance_suite_error_names_its_package`.
- [ ] JavaScript or Dart code in a new top-level folder that `sources` does not list stops the check and names the folder → `tests/test_greenfield.py::test_javascript_and_dart_code_added_after_setup_must_join_the_checked_sources`.

Slice 4, gate reports:

- [ ] A pytest run that finds no test gets no parallel hint → `tests/test_report_findings.py::test_a_run_with_no_tests_gets_no_parallel_hint`.
- [ ] A failed secret scan prints the rule, file and line of each finding and never the secret → `tests/test_report_findings.py::test_a_failed_secret_scan_names_rule_file_and_line`.
- [ ] A failed React Doctor gate prints file, rule and message from its report → `tests/test_report_findings.py::test_a_failed_react_doctor_gate_prints_its_findings`.
- [ ] A failed Fallow gate prints the file and the unused export or dependency → `tests/test_report_findings.py::test_a_failed_fallow_gate_prints_its_findings`.
- [ ] A failing Flutter widget test prints the reason from its print events and its file and line → `tests/test_dart_test_report.py::test_a_failing_widget_test_gives_its_reason_and_file`.

Slice 5, debt, Stop text and small command faults:

- [ ] A debt paid down to one finding passes `check`, the adopt shrink and the shrink-only check, for the real ruff, pyrefly, Biome and `dart analyze` lines of Same cause (4) → `tests/test_debt.py::test_a_count_word_for_one_or_many_is_the_same_debt_line`.
- [ ] Stop lists no gate that the debt forgave, and shows the "findings beyond" lines → `tests/test_stop_checks.py::test_stop_lists_only_gates_with_findings_beyond_the_debt`.
- [ ] The Stop text holds no terminal colour codes → `tests/test_stop_checks.py::test_stop_text_has_no_colour_codes`.
- [ ] The Bun freshness repair command names each package once and has `-r` when the gate has it → `tests/test_freshness.py::test_the_bun_repair_command_covers_a_workspace_once`.
- [ ] A change to `hard-eng.debt.json` does not count toward the size → `tests/test_change_size.py::test_the_debt_file_does_not_count_toward_the_size`.
- [ ] A missing `uv` program is named in the error → `tests/test_tool_environment.py::test_a_missing_uv_is_named`.

Slice 6, plans and requirement IDs:

- [ ] A one-part `HE-` ID is checked: an unknown one is named, and `HE-YAGNI` is a registry entry → `tests/test_requirements.py::test_one_part_he_ids_are_checked`.
- [ ] A registry heading that starts with `REQ-` or `HE-` and is not a valid ID is an error that names it → `tests/test_requirements.py::test_a_registry_heading_with_a_malformed_id_is_refused`.
- [ ] The requirements intro states the ID format → N/A — reference text; the Reader check goes in Verification.
- [ ] On the default branch with `origin/<base>` present, a Complete plan in an unpushed commit covers a later uncommitted fix → `tests/test_plan_acceptance.py::test_an_unpushed_plan_on_the_default_branch_covers_a_later_fix`.
- [ ] A passing quick check, and the Stop that runs it, say that the quick checks passed and that tests run in the full check; a full Complete check still says ready for ship → `tests/test_plans.py::test_native_cli_plan_stage_and_missing_plan`.

Slice 7, Trello text checks (last, by the coordinator):

- [ ] A link inside a sentence is not read for technical words or code marks → `tests/test_trello_board.py::test_a_link_inside_a_sentence_is_not_read_for_technical_words`.
- [ ] The run reference's worktree test works from a subfolder → N/A — skill text; the Reader check and one run of the command from a subfolder go in Verification.
- [ ] The run reference says to run `update-pr` again when the checks have not finished → N/A — skill text; the Reader check goes in Verification.

Steps:

1. Each builder takes its slice in its own worktree.
2. For each item, the builder first writes the test and sees it fail on `develop` for the audit's reason.
3. A builder who needs a line in a file or function that another slice owns stops and asks the coordinator.
4. After the join, the coordinator times session start and Stop, old against new.
5. The coordinator joins the slices in order 3, 1, 2, 4, 5, 6, 7 and runs the full check once.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` ef95cd12, the merge of the session start fix. On that commit the `hard-eng` and `canary` CI checks passed on 2026-11-10 after a rerun. The first two runs stopped before any check: the npm registry listed a mise release whose Linux file was not there yet. `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch, with this plan as the only change: exit 0, with 20 gates, 2,424 tests and 91.91% line coverage.
Execution: six builders on Sonnet, each in its own worktree; the coordinator does slice 7. A fresh Opus reviewer reads the joined diff, and a second one reads the tests. A reader who did not write the texts runs the Reader check. Files have a limit of 1,000 lines. `.hooks/gate_config.py` is at 997, `.hooks/project_setup.py` at 996, `setup.py` at 995, `.hooks/agent_hooks.py` at 993, `.hooks/hard-eng.py` at 990, `.hooks/plans.py` at 978, `tests/test_update_pr.py` and `tests/test_ship_actions.py` at 996, `tests/test_reports.py` at 984 and `tests/test_plans.py` at 974. A builder moves code to the owner module that has room before it adds lines to one of them; new tests for a full file go in the new test file that its acceptance line names. Three slices edit `.hooks/hard-eng.py`, each in its own function: slice 3 adds at most 3 lines after a failed gate, slice 2 adds at most 2 lines in the `check` branch of `main`, and slice 6 changes the `report_stage` call with no new line. Two slices edit `.hooks/agent_hooks.py`, each in its own function: slice 5 in `failure_summary` and `bounded`, slice 6 in `completion_notice`.

- Slice 1, updates: `.hooks/update_pr.py`, `.hooks/update_runner.py`, `.hooks/update.py`, `tests/test_update_pr_refusal.py` (new), `tests/test_update_runner.py`, `tests/test_updates.py`.
- Slice 2, shipping and stop signals: `.hooks/shipping.py`, `.hooks/review_bypass.py`, `.hooks/ship_actions.py`, `.hooks/process_group.py`, `main` in `.hooks/hard-eng.py`, `tests/test_shipping.py`, `tests/test_ship_cleanup.py` (new), `tests/test_check_signals.py` (new).
- Slice 3, gates and setup: `.hooks/gate_config.py`, `.hooks/project_setup.py`, `.hooks/python_setup.py`, `configure_shellcheck` in `setup.py`, the gate result in `.hooks/hard-eng.py`, `.agents/skills/he/references/gates.md`, `tests/test_package_discovery.py`, `tests/test_basic_mode.py`, `tests/test_husky_setup.py`, `tests/test_greenfield.py`.
- Slice 4, gate reports: `.hooks/reports.py`, `.hooks/react_report.py`, `.hooks/fallow_report.py`, `.hooks/dart_test_report.py`, `tests/test_report_findings.py` (new), `tests/test_dart_test_report.py` (new).
- Slice 5, debt, Stop text and small faults: `.hooks/debt.py`, `failure_summary` and `bounded` in `.hooks/agent_hooks.py`, `.hooks/freshness.py`, `.hooks/change_size.py`, `.hooks/tool_setup.py`, `tests/test_debt.py`, `tests/test_stop_checks.py`, `tests/test_freshness.py`, `tests/test_change_size.py`, `tests/test_tool_environment.py`.
- Slice 6, plans and requirement IDs: `.hooks/plans.py`, the `report_stage` call in `.hooks/hard-eng.py`, `completion_notice` in `.hooks/agent_hooks.py`, `.agents/skills/he/references/requirements.md`, `tests/test_requirements.py`, `tests/test_plan_acceptance.py`, `tests/test_plans.py`, `tests/test_agent_hooks.py`.
- Slice 7, Trello text checks: the text check in the coordinator skill's scripts, its run reference, `tests/test_trello_board.py`.

Dependencies: none between the builders; no two slices share a function. Slice 7 starts after a fetch, because other work changes the coordinator skill.

## Risks + recovery

- An installed JavaScript or Dart project with code in a top-level folder or file that `sources` does not list fails `check` after the update, until it lists it and its tests cover it. The message names it and the step. The update PR of such a project shows the failure before the merge. Recovery: revert the guard's own commit.
- A gates file with no package, in a project that added a shell script, a workflow or a deployment file after install, fails `check` after the update, until it has the gate. The message names the step.
- A registry heading such as `## REQ-1` in a project's `docs/requirements.md` becomes an error that names the format.
- These three changes can turn an installed project red after the update. The PR text and the release text name all three with their steps.
- A one-part `HE-` token in a project's Markdown that is not a rule is now reported as unknown. The design review found none in this repository or in five installed fixtures.
- Two debt lines that differ only in the ending of the count word now count as one line. No tool in the probe prints such a pair.
- Uncertainty: a new check in the validation can slow session start. Cheapest check: time the real hook command, old against new, with compiled modules, 40 alternating runs, medians. The fixtures are a Flutter scaffold, a Next.js scaffold and a basic mode project with about 2,000 files, 200 of them with no suffix. If a median grows, that check moves to `check` only (Decided 15).
- Uncertainty: the host may stop `check` with a signal other than SIGTERM or SIGHUP. Then its gates still live on, as today.
- After Ctrl-C at a push through the Python launcher, the pre-push sends SIGTERM to its `check` before the launcher kills the pre-push. If the kill comes first, the gates run to their end, as today.
- Old Complete plans name tests in files that this round does not rename. No test is removed.
- Recovery for any slice: revert its commit.

## ux_reference

N/A — hook, command and message changes with no visual surface.

## Verification

Result: Pending
Evidence: Pending — each new test's failing run on `develop` and its passing run after the fix, the focused runs per slice and the full check on the joined branch. Also one run in a new Python project that adds its first module and follows the two messages until `check` passes. Also the canary run of every `--new` scaffold with the sources guard, and the names of the tests that Decided (4) changed. Also the Reader checks of the gates reference, the requirements intro, the two run reference lines and the three reworded refusals, and one run of the worktree command from a subfolder.
Speed: Pending — session start old against new in the three fixtures of Risks, and Stop with a failing gate old against new, 40 alternating runs each, medians.
E2E: N/A — no user journey changes; each behavior is a hook, command or setup result that its test runs directly.
Retro: Pending — written at task end per HE Learn's Retro section, before the plan is set to Complete.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the release into `main`.
