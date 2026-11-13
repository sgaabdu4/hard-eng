# Nine open faults from real use

Status: Ready

## Outcome + scope

The nine open faults that real use found (issues 589, 590, 593, 594, 595, 596, 605, 606 and 607) are repaired, each with a test that failed before its repair. Non-goals: a split of the files near the size limit, the faults of a runner host, new rules.

## Repository context

Owners: the update and setup path (`.hooks/update.py`, `.hooks/hook_chain.py`, `.hooks/agent_hooks.py`, `.hooks/change_size.py`) for 589 and 590; the Git calls of the hook events for 593; `.agents/skills/he/semgrep/performance.yaml` and `.agents/skills/he/references/efficiency.md` for 594 and 596; `.hooks/fallow_report.py` for 595; `.hooks/shipping.py` and `.hooks/review_bypass.py` for 605 and 606; `tests/test_shards.py` for 607. Evidence: the text of each issue, with its reproduction.
Same cause: 589 → issue 414 repaired only the shell gate message (helped for that message); the launcher stayed outside the update commit. 590 → the seen case got its own repair (the Python dead-code role accepts a second scanner; helped for that case); the missing load check stayed. Other places where setup or the update judge a project file with fewer rules than the later load are searched in this change. 593 → no earlier fix; each Git command of the hook events is covered, not only the two listings of the issue. 594 → no earlier fix; the messages of the same rule in the other languages are read for a form that changes the error behavior. 596 → no earlier fix; each Dart pass form that names a call which can take a type argument (`Future.delayed`, `Future.wait`) gets its typed form in this change. 595 → no earlier fix; the size rule and the JavaScript source list already read the generated mark. 605 → the `update-pr` reader and the `ship ready` reader were each changed for a cancelled run (helped for those readers); `_checks` also serves `passed_branch_point`, which keeps its present read. 606 → no earlier fix; the order of the other refusal texts in `bypass_problem` is checked in this change. 607 → no earlier fix; each other test of `tests/test_shards.py` that starts a real inner run is timed.
Single source: the load rules of the gates file have one owner, the load in `.hooks/gate_config.py`; `validate_gates` in `.hooks/update.py` calls that load and holds no second list of rules. The generated mark has one reader, `generated_sources` in `.hooks/gate_config.py`; the Fallow check calls it. The accepted Dart join form has one text owner, the efficiency reference; the rule message names the same form. The watcher setting for hook Git calls gets one owner. Paths searched for copies: `.hooks/`, `.agents/skills/he/`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 13 November the maintainer said that the tool must be great and that the work stays in one session; the maintainer gave full authority for design choices earlier. Merge when the checks pass is a standing approval.

Decided:

1. 593: the Git commands of a hook event run with the file watcher off, set at one owner. No hook command may rewrite the index. A project without the setting gets no added hook time.
2. 590: before the update builds its commit, it loads the gates file, as the update will leave it, with the full load of the new release. A file that cannot load gives the printed refusal with the rule text and one repair step, and the project stays on its release.
3. 589: when the hooks folder is inside the work tree, the update commit carries the worktree launcher, the kept copy of a project hook and the shell gate line. A checkout that already has those files uncommitted is clean after its next update.
4. 594: the message and the reference name an eager join that throws the first error at once with its own type: `Future.wait` with `eagerError: true`, then a read of each result. They no longer name a record's `.wait`. The reference states the plain form for two ordered steps that return values.
5. 596: the pause pass form of the Dart loop rule also accepts `await Future<T>.delayed(...)`, in the same three loop forms. Each new pass form names its exact call.
6. 595: the Fallow check sets aside a clone group when each instance of it is in a file with the generated mark. A group with one instance in hand-written code still fails. Setup writes nothing into the Fallow settings of a project.
7. 605: the delivered stage judges, for each required check, the run that the push to the base branch started. A run that another pull request started on the same commit is not read. A check with no push run is judged as before.
8. 606: `ship ready` reads the head checks before the review rule. A check that still runs gives a refusal that names the check and says to wait and run the stage again.
9. 607: the worker-count test proves the same result with a smaller inner run. No limit is raised.

## Acceptance + steps

- [ ] 593: no hook event asks the Git file watcher of a project that has it on → `tests/test_git_watcher.py::test_no_hook_event_asks_the_git_file_watcher`
- [ ] 593: the hook events leave the Git index file as it is → `tests/test_git_watcher.py::test_the_hook_events_leave_the_git_index_unchanged`
- [ ] 593: a project without the setting gets no added hook time → N/A — a test cannot show a part of a millisecond; Verification records the module list, the call counts and the timed runs of both versions.
- [ ] 590: an update is refused with the rule text and one repair step when the gates file cannot load under the new release, and the project stays on its release → `tests/test_update_gates_load.py::test_an_update_is_refused_when_the_gates_file_cannot_load_under_the_new_release`
- [ ] 590: an update still lands when the gates file loads → `tests/test_update_gates_load.py::test_an_update_lands_when_the_gates_file_loads_under_the_new_release`
- [ ] 589: after the update commit is on the default branch, the main checkout of a project with a tracked hooks folder is clean, and the size rule asks for no plan → `tests/test_update_hooks_folder.py::test_the_main_checkout_is_clean_after_an_update_with_a_tracked_hooks_folder`
- [ ] 589: the update commit carries the kept copy of a project hook → `tests/test_update_hooks_folder.py::test_the_update_commit_carries_the_kept_copy_of_the_project_hook`
- [ ] 589: the update commit carries the shell gate line of the launcher → `tests/test_update_hooks_folder.py::test_the_update_commit_carries_the_shell_gate_line_of_the_launcher`
- [ ] 589: a checkout that already has the untracked launcher is clean after its next update → `tests/test_update_hooks_folder.py::test_a_checkout_with_an_untracked_launcher_heals_with_the_next_update`
- [ ] 589: a hooks folder outside the work tree adds nothing to the update commit → `tests/test_update_hooks_folder.py::test_a_hooks_folder_outside_the_work_tree_adds_nothing_to_the_update_commit`
- [ ] 594: the Dart message names a join that keeps the first error and no form that holds it back → `tests/test_hot_paths.py::test_the_dart_join_message_names_a_form_that_keeps_the_first_error`
- [ ] 594: a worker that gets the new message writes a join that throws the first error at once → N/A — no local test can run a model; Verification records the worker runs with the old and the new message.
- [ ] 596: a poll loop with a typed pause passes the Dart loop rule, and a typed call that is no pause still gives a finding → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`
- [ ] 595: a clone group whose instances are all in generated files is set aside → `tests/test_report_findings.py::test_a_clone_group_in_generated_files_only_is_set_aside`
- [ ] 595: a clone group with one hand-written instance still fails → `tests/test_report_findings.py::test_a_clone_group_with_one_hand_written_instance_still_fails`
- [ ] 605: the delivered stage passes when the push run passed and a run of another pull request failed on the same commit → `tests/test_shipping_delivered.py::test_delivered_judges_the_push_run_when_a_run_of_another_pull_request_failed`
- [ ] 605: the delivered stage still refuses when the push run failed → `tests/test_shipping_delivered.py::test_delivered_refuses_when_the_push_run_failed`
- [ ] 605: a check with no push run is judged as before → `tests/test_shipping_delivered.py::test_delivered_judges_a_check_with_no_push_run_as_before`
- [ ] 606: `ship ready` names the required check that still runs and not the review rule → `tests/test_review_bypass.py::test_a_check_that_still_runs_is_named_before_the_review_rule`
- [ ] 606: the review text stays when each head check passed → `tests/test_review_bypass.py::test_the_review_text_stays_when_each_head_check_passed`
- [ ] 607: the worker-count test proves the same result with a smaller inner run → `tests/test_shards.py::test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact`
- [ ] 607: the `tests` gate is clearly under its limit → N/A — a time on one machine; Verification records the time of the test and of the gate before and after.

## Baseline + execution

Result: Passed
Evidence: develop 9e73c7a2: the Hard Eng CI run for the push of that commit passed, and `ship --stage delivered` passed on it on 13 November. This branch starts there. Each static gate command of the gates file gave exit 0 on that commit before the first edit.
Execution: three investigations first (589, 590, 593), each by a reader that changes nothing. Then builders in their own worktrees: one for 605 and 606, one for 594 and 596, one for 595, one for 607, one for 593, and one for 590 then 589, because both touch `.hooks/update.py`. The coordinator joins the commits in that order and runs the static gates and the whole suite on the joined branch. One independent review before the final gate.

## Risks + recovery

- 593: a Git command with the watcher off scans the whole tree. In a very large project that can cost more than the watcher saves; the investigation measures 100,000 files before the build.
- 590: a load rule that needs an installed tool or the network could refuse an update for a cause outside the gates file; the load in the update must skip those parts or the design changes.
- 589: the update commit must take in no file that the project owner wrote, other than the copy of the owner's hook that setup made.
- 605: one more API read in the delivered stage.
- Recovery: each repair is its own commit; revert that commit.

## ux_reference

N/A — command output and rule texts only; no visible UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no app journey changes; each repair has a test at the command that real use ran.
Retro: Pending.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop, then `ship --stage delivered` passes on the merged commit.
