# Stop a hook's child from failing the background update

Status: Ready

## Outcome + scope

The background update no longer ends with `Hard Eng update failed: [Errno 66] Directory not empty: '<tmp>/hard-eng-update-<x>/candidate'` when a git hook of the project leaves a child that still writes in the update's private worktree. Non-goals: the update lock, the update steps, and the order of session start.

## Sources + coverage

Sources: N/A — a client report relayed in the task brief: several sessions started together, two `update` processes and two `hard-eng-update-*` folders were seen, and session start printed the failure line above.
Deliverables: None

## Repository context

Owners:
- `.hooks/update_runner.py` `build_update` and the new `candidate_worktree` own the private worktree of an update.
- `.hooks/update_pr.py` `tip_refusal` made the same kind of worktree on its own; it now uses `candidate_worktree`.
- `.hooks/tidy_guards.py` `open_files`, `open_paths` and the new `stop_inside` scan which process holds a path.
- `.hooks/update_runner.py` `lock_file`, `exclusive`, `run_update` and `locked_update` own the one-update lock.

Same cause: Searched for every place that makes a `hard-eng-update-*/candidate` worktree: `build_update` (background update and `update-pr`) and `tip_refusal` (the check of the update branch before a push). Both now go through `candidate_worktree`. The three other `hard-eng-update-*` folders (`update.py` source fetches and `revision_follows`) hold bare clones and fetched trees, not a worktree that runs git hooks, so no hook child can start in them. `hard-eng-push-*` snapshots in `ship_actions.py` have the same shape and are outside this task.
Single source: Making, locking and removing the private worktree of an update lives only in `candidate_worktree`. Before this change `build_update` and `tip_refusal` each held a copy; both copies are merged here.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; a client project's session start printed an update failure.

## Acceptance + steps

Cause, found by a real run: a hook child outlives its git command. The update removed the worktree while that child still created files in it. `git worktree remove` printed `failed to delete ... Directory not empty` (its exit code was ignored) and the temporary folder removal then raised `[Errno 66]`, which replaced the real result. The supervisor stops leftover children only after the update has exited, which is too late for this removal.

Lock question (brief step 1), answered by real runs: the exclusive lock is taken by the supervisor (`run_update`) before it starts the update, and `locked_update` takes the same lock for `update-pr` and setup. Five worktrees started at staggered times over six releases, and two worktrees started at the same moment, each ended with one update and no failure; the others print "Another Hard Eng update is already running". One update is two processes by design (the supervisor and its `--apply` child) and makes two `hard-eng-update-*` folders (the private worktree and the fetched source), which is what the client saw. `tip_refusal` was the one route that made a candidate with no lock and no owner; it now shares the cleanup.

Proof that the writer is inside Hard Eng's control: the child starts inside the update's own commits and worktree creation, in a worktree that Hard Eng made and owns. A process of another account cannot be stopped and stays; then the error still shows and is not hidden.

- [ ] A child left by a project's post-commit hook does not fail the update, and no private folder or worktree stays → `tests/test_update_race.py::test_a_hook_child_in_the_private_worktree_does_not_fail_the_update`.
- [ ] The same for the check of the update branch → `tests/test_update_race.py::test_the_check_of_the_update_branch_leaves_no_child_in_its_worktree`.
- [ ] Two session starts at the same moment end with one update commit, one ready result and no failure line, with the same hook child → `tests/test_update_race.py::test_two_session_starts_together_run_one_update_and_print_no_failure`.
- [ ] A child that a stopped process forks while the stop runs is stopped too → `tests/test_update_race.py::test_a_stop_signals_a_child_that_a_stopped_process_forked_meanwhile`.
- [ ] A scan that takes longer than the wait still signals what it found, once per signal → `tests/test_update_race.py::test_a_slow_scan_still_signals_the_processes_that_it_found`.
- [ ] A host that cannot list processes still lets the removal go on → `tests/test_update_race.py::test_a_host_that_cannot_list_processes_still_lets_the_removal_go_on`.
- [ ] A process of another account does not hide the update's own processes from the stop → `tests/test_update_race.py::test_a_process_of_another_account_does_not_hide_ours`.
- [ ] The private worktree stays locked until its processes are stopped, so an interrupted update leaves it to the stale sweep with its owner → `tests/test_update_race.py::test_the_private_worktree_is_unlocked_only_after_its_processes_stop`.
- [ ] A clean update still starts detached, and a running update is reported, not duplicated → `tests/test_update_runner.py::test_start_detaches_worker_without_inherited_pipes` and `tests/test_update_runner.py::test_running_update_is_reported_not_duplicated` (existing, unchanged).
- [ ] The tidy keeps its answer about busy worktrees after `open_paths` moved onto `open_files` → `tests/test_tidy.py::test_an_unreadable_process_counts_as_unknown_only_for_another_person` (existing, unchanged).

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` 214f5aef the three new tests fail with the client's exact line (`Hard Eng update failed: [Errno 66] Directory not empty: '.../hard-eng-update-<x>/candidate'`); the stress run of five worktrees and six releases and the plain two-start run pass on the same code, so the lock was not the cause.
Execution: One builder in a separate worktree of the repository: tests first, then `tidy_guards.py`, `update_runner.py`, `update_pr.py`, then challenge and the Complete check.

## Risks + recovery

`stop_inside` stops processes of the same account that hold a file or folder in the private worktree; the worktree is made and owned by the update, so only its own hook children are there. It signals again each pass, so a child forked meanwhile is caught, and it waits 3 seconds for each signal, under the 10 seconds that the supervisor gives an interrupted update. A host with neither `/proc` nor `lsof`, or a failed `lsof`, cannot list holders, so nothing is stopped and the old behaviour stays (the error is not hidden). Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — hook Python logic has no user interface.

## Verification

Result: Pending
Evidence: Pending — focused tests, static gates, challenge and the Complete check.
E2E: N/A — background hook with no interactive journey; the tests start real supervisor and update processes over real git worktrees.
Real service: N/A — no changed code calls an outside service.
Retro: Pending

Delivery target: Merge
Delivery: Pending — checks, challenge, PR to `develop`, CI and merge.
