# Reuse a passed full check at Stop, refuse shard settings in a local check, and fix the faults of audit round thirteen

Status: Ready

## Outcome + scope

A Stop does not run its quick checks again when a full check passed on the same commit, the same base and a clean tree in the last 30 minutes. Each Stop starts fewer Git processes: 5 where it started 7 with no change, and 6 or 7 where it started 10 with a change. A local check of a gate with `shards` refuses a test path and a moved option that tracked files hold, so the first refusal no longer comes in CI. An audit of the released code runs in sealed copies of real projects; each fault that it reproduces in normal use is fixed, with a failing test first. Non-goals: no record of a passed quick check, no reuse when the full check used an older base, no reuse for a Stop of a build in progress, no change to the shard split, and no change to `.hooks/plans.py`.

## Repository context

Owners: `.hooks/process_group.py` owns the record of a full pass (`hard-eng-passed`, beside the check lock): `clean_start` and `record_pass` write it, and `passed_minutes` reads it for the push check. `.hooks/agent_hooks.py` owns the Stop: `completion` finds the base with `session_scope`, lists the changed files and calls `checked_changes`, which opens the check lock in `check_is_running` and then starts `check --quick`. `.hooks/ship_actions.py` owns `spared`, the push check line "the full check passed on this exact commit and base". `.hooks/shards.py` owns `require_no_path` and `require_default_settings`; today only `part_command` calls them, and `.hooks/gate_runner.py` calls `part_command` only for a run with `--shard`. `.hooks/ci_cache.py` owns the note "CI tool directories", and `migrate_tool_environment` in `.hooks/ci_setup.py` removes a job env line of a tool directory when the workflow holds the step form. `.agents/skills/he/references/gates.md` owns the shard paragraph; the file is 23 bytes under the limit of 36,000 bytes for one skill file.
Same cause: three causes. (1) A Stop pays again for proof that exists. Earlier fixes: the session record of the last passing Stop check ("unchanged since last passing check") and the push check line of `spared`, which reuses a full pass of the same commit and base; both helped, and no Stop read the full pass. Other places, searched: the push check (has the reuse), the CI runs of a merged commit (reuse the pass of the PR head), `ship` (reads the record of the independent review), and the Stop, which this plan fixes. The Stop also starts Git processes whose answer it already holds: the parent of the oldest commit that is not pushed, an ancestor question whose answer is yes, the commit ID that its own session file holds, and a second listing of the plan files; slice 1 removes them. (2) A rule that only one path runs. The shard refusals of round twelve run in a shard job and in the merge, so a local check passes a setting that CI refuses; the round twelve fix helped for CI and its PR named this gap. Other places, searched: each other refusal of `.hooks/shards.py` runs from `part_command` only for a shard run and needs the shard reports, so it stays there. (3) A printed step that is not the whole step. Round twelve fixed five printed steps and gave each a test of its text; that helped for those steps. The tool directory note is one of the five: its step now has the right syntax, but it does not say that the named lines must go, and after the step the note is silent while the lines stay. Other places: the audit brief keeps the line "do exactly the step that each message names", and the audit of this round did each printed step of an update in five project copies.
Single source: `fresh_pass` in `.hooks/process_group.py` is the one reader of the full pass record; `passed_minutes` and the Stop both use it. `passed_note` there owns the sentence "the full check passed on this exact commit and base"; `spared` and the Stop print it. Searched: `PASSED_FILE`, `passed_minutes` and the sentence in `.hooks/` and `tests/`; no other copy. The refused shard options keep their one owner, the constants of `.hooks/shards.py`. The tool directory note keeps its one owner, `tool_directory_messages`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer said that speed is important, that each change is timed old against new, and that the builder makes the decisions.

Decided:

1. The Stop reuses the record that the push check already uses. A full check writes it only for a pass at no stage or at Complete, on a clean tree, outside CI, and it holds the commit, the base commit and the start time. No new record of a passed quick check: its key would need the file hashes of a session, which a manual check does not make.
2. The Stop reuses the pass only when the record base equals the Stop base. A full pass against an older base is not always a pass against a later base: the debt rule, the comment rule, the suppression rule and the plan rule compare with the content at the base, so a line that was removed before the later base and added again after it passes against the older base and fails against the later one. Recorded, not built: reuse when the record base is an ancestor of the Stop base.
3. A Stop of a build in progress runs its check as before. Its check uses the stage Ready, and the record is of the stage Complete or of no stage.
4. A Stop still gives the block of a held check lock before it reads the record.
5. A Stop that still runs its check starts no more Git processes than before. The order of the tests gives this: the record is read beside the lock file that the Stop already opens; the commit comes from the base search; a file that Git does not track comes from the listing that the Stop already has; the base compare is a text compare; `git status` runs last and only when each other test passed. A count of Git starts on each path is the proof, old against new.
6. The base search asks Git one time for the commits that are not pushed, with their parents, so it needs no second call for the parent of the oldest one. When the commit before the first commit that is not pushed is the session base, the search skips the ancestor question, because the answer is yes. The search also gives the commit of HEAD. A Stop does not ask Git to resolve a session base that is a full commit ID, because the session start wrote the ID that Git gave; each other form, such as `HEAD` of a session that began outside the project, is still resolved. When Git cannot read the base, the Stop still blocks with the reason. One Stop keeps its file listings, as one check does, so it lists the plan files one time.
7. A reuse goes through the same lines as a passed check: the session file of a session that began outside the project, the record of the last pass, the block for accepted decisions, and the notice. The notice is the sentence of the push check.
8. A plain local check of a gate with `shards` calls the two refusals before the gate command runs, for the settings that tracked files hold: the command and the pytest `addopts`. It does not read `PYTEST_ADDOPTS` and `COVERAGE_RCFILE`: a variable of one local shell does not reach the CI job, and the shard job still refuses each one. The refusals do not run at the settings load, because each session start loads the settings.
9. The tool directory note tells the person to replace the named lines with the step. Recorded, not built: a setup rerun with no newer release that writes the planned removal, and a note that reads the file when the run writes nothing; with the whole step in the text, the half-done state needs a person who does only a part of the printed step.
10. Not a Hard Eng fault, by the rule that the project changes when a project change can pass: a project keeps the support files of its browser tests in a folder with its own name, and the sources rule calls them production code. The refusal already names the test folders, and the move to one of them passed in the project copy. A Flutter driver folder was a fault in round twelve because the Flutter tool fixes its name.
11. Recorded and not built, each with its reason: a record of a passed quick check (decision 1); the shard paragraph of the gates reference in its own file (the changed sentence fits); a time weight for the shard split (needs stored times); a clear text for a setup rerun whose recorded release the source no longer holds, and for a failed fetch of a pinned skill commit (both rare); `update-pr` with no shipping block on the base (rare); setup prints its CI notes two times outside a check (a repeat, no wrong result); `-c` inside a group of short options and a retry count of zero on the next line (rare forms).

## Acceptance + steps

Constraints: the limit is 1,000 lines for each file; `.hooks/agent_hooks.py` has 962 lines and `.hooks/plans.py` 1,000, so this plan adds at most 30 lines to the first and none to the second. No hook path gets slower: each path of a Stop is counted and timed old against new. Each reference file stays under 36,000 bytes.

Slice 1, the Git processes of a Stop (`.hooks/agent_hooks.py`):

- [ ] The base search starts one Git process when the session began at the branch point, and two when the pushed commit is not the session base → `tests/test_stop_checks.py::test_the_base_search_asks_git_one_time_at_the_branch_point`
- [ ] The base search gives the same base as before and the commit of HEAD: for a branch with no pushed commit, for a pushed branch, for a first commit that has no parent, and for a branch that merged its base → `tests/test_stop_checks.py::test_the_base_search_gives_the_base_and_the_commit_of_each_history`
- [ ] A Stop with no change starts 5 Git processes and none to resolve its session base; a Stop with a change starts 7 and lists the plan files one time → `tests/test_stop_checks.py::test_a_stop_asks_git_for_no_answer_that_it_holds`
- [ ] A Stop still blocks with the reason when Git cannot read the session base, with a remote and with none → `tests/test_stop_checks.py::test_a_stop_blocks_when_git_cannot_read_the_session_base`

Slice 2, a Stop reuses a full pass (`.hooks/process_group.py`, `.hooks/agent_hooks.py`, `.hooks/ship_actions.py`):

- [ ] A Stop with a full pass of the same commit, the same base and a clean tree runs no check, shows the sentence of the push check, and the next Stop says "unchanged" → `tests/test_stop_reuse.py::test_a_stop_reuses_a_full_pass_of_this_commit_base_and_tree`
- [ ] A Stop runs its check when the full pass is of another commit, of another base, older than 30 minutes or absent, when a tracked file changed after the pass, when a new file exists, and when a build is in progress; only the changed tracked file costs one `git status` → `tests/test_stop_reuse.py::test_a_stop_runs_its_check_when_no_full_pass_covers_it`
- [ ] A held check lock still blocks a Stop that has a full pass → `tests/test_stop_reuse.py::test_a_held_check_lock_blocks_a_stop_with_a_full_pass`
- [ ] The push check still reuses a full pass and prints the same sentence → `tests/test_push_check.py::test_a_full_check_that_passed_on_the_pushed_commit_spares_the_push_check`

Slice 3, shard settings in a local check (`.hooks/shards.py`, `.hooks/gate_runner.py`, `tests/test_shard_local.py`, `.agents/skills/he/references/gates.md`):

- [ ] A plain check of a gate with `shards` refuses a test path and each moved option in the command and in `addopts`, with the text of the shard job, before the gate command runs → `tests/test_shard_local.py::test_a_local_check_of_a_shard_gate_refuses_what_tracked_files_hold`
- [ ] A plain check of a gate with `shards` passes with `PYTEST_ADDOPTS` or `COVERAGE_RCFILE` set, and a gate with no `shards` keeps each option → `tests/test_shard_local.py::test_a_local_check_reads_no_variable_and_no_gate_without_shards`
- [ ] The gates reference says which refusals each run makes and stays under the size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`

Slice 4, the faults that the audit reproduced, each with its failing test first:

- [ ] The tool directory note tells the person to replace the named lines, and a workflow with the step done as printed gets no note and no pending change → `tests/test_ci_cache.py::test_the_tool_directory_step_done_as_printed_leaves_no_note_and_no_pending_change`

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 8f7e2241, the rebase merge of PR 581. On that commit the required CI checks passed on 2026-11-12: each push run reused the pass of the PR head on the same files, and that head passed the checks job, each of the six shard jobs, the merge of their reports and each new-project job. `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on this branch, with this plan as the only change: exit 0.
Execution: the coordinator builds slices 1, 2 and 4, with a failing test before each behavior, and counts and times each Stop path old against new. One builder on Sonnet in its own worktree builds slice 3, with each static gate command in its brief. Audit agents on Opus run in sealed copies in seven areas; each reproduced fault of normal use joins slice 4. A new reviewer on Opus reads the joined change, the independent review runs on the final commit, and the Complete check runs once.

## Risks + recovery

- A Stop reuses a pass that does not cover its change. Recovery: the reuse needs the same commit, the same base, a clean tree by `git status` and a record of at most 30 minutes; the second test of slice 2 has one row for each condition, and each row must run the check.
- A full check writes the record while a file changes. Recovery: none new; `record_pass` already writes only when the tree is clean at the start and at the end and the commit is the same.
- A session file holds a commit ID that Git no longer has. Recovery: the ancestor question or the file compare fails, and the Stop blocks with the reason; the last test of slice 1 has one row for each.
- The one Git call with parents gives another base than the two old calls. Recovery: the second test of slice 1 gives the base of each history, and the old and the new search are compared on real histories before the review; the PR gives the number of histories and how many agree.
- A project already holds a refused option on a gate with `shards`, and its local check now fails. Recovery: its shard job already fails with the same text; the refusal names the option and the step.
- The changed sentence of the gates reference passes the size limit by a few bytes. Recovery: the size test runs after each edit of the file; if the clear sentence does not fit, the shard paragraph moves to its own reference in this plan.

## ux_reference

N/A — hook results, check rules and printed lines with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey changes; each behavior is a hook result, a check or a printed line that its test runs directly.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — the PR checks pass on the final commit, `ship` passes its ready stage, the rebase merge into `develop` and the release merge into `main` pass their runs.
