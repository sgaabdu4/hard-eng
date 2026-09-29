# Keep session hooks from blocking the agent and refresh the Playwright pins

Status: Complete

## Outcome + scope

Starting, resuming or compacting an agent session no longer waits on the scaffold update (issue 213). SessionStart records the session's Git base, reports the last update result, and starts one detached supervisor per repository. The supervisor holds the update lock and runs the update in its own process group; the update still verifies an isolated candidate and makes its own local commit. Interrupting it stops every process it started (SIGTERM, then SIGKILL after 10 seconds), removes its candidate worktree and records the outcome. Candidates are locked with their owner's PID, so only those whose owner exited are removed, never a live or legacy updater's. A failed update commit keeps any edit made while it ran instead of rolling it back, and an interruption after the commit keeps the commit. The update commit does not count as the session's own work, and Stop says an update is still running instead of asking for another. Ending a turn that changed nothing since the session's last passing check no longer reruns the full check, and an interrupted Stop hook stops every process the check started (issue 216). The two video skills pin Playwright 1.63.0 with regenerated lockfiles (issue 196).

Non-goals: a shorter SessionStart registration timeout (the hook no longer does network or verification work, and changing the registered entry would need a Claude hook migration), a scheduled dependency updater for skill manifests (issue 196's optional suggestion; it is new infrastructure without an agreed requirement), and rechecking only affected gate groups or shortening the Stop budget (issue 216's optional suggestions; skipping unchanged turns removes the repeated runs).

## Repository context

Owners:
- `.hooks/agent_hooks.py` `session_context`: called `update(root)` inline, so the SessionStart hook ran clone, submodule fetches and the full candidate check (up to 3500s) before the agent could start.
- `.hooks/update.py` `verify_candidate` + `commit_update`: the candidate `worktree add`, submodule update and `worktree remove` had no timeout, cleanup relied on `finally`, which a signal skipped, and a failed commit restored every managed file unconditionally. `update.py` was already at the 1000-line file limit, so the runner and the commit transaction live in `.hooks/update_runner.py`.
- `.hooks/agent_hooks.py` `completion` + `run_check`: every Stop compared the tree with the session-start snapshot, so once a session changed a file each later turn reran the full check; the check ran inline without its own process group.
- `.hooks/update.py` `require_current`: Stop's freshness check, which told the agent to rerun the updater.
- `setup.sh`: the fallback installer path, now serialized with the background update.
- `AGENTS.md` and `README.md`: described a synchronous startup update.
- `.agents/skills/{product-walkthrough-video,marketing-video}/package.json` + `pnpm-lock.yaml`: pinned `playwright` 1.62.1.
- `.agents/skills/product-walkthrough-video/scripts/walkthrough-pointer.mjs` `moveMouseWithDuration`: sent a fixed 60 mouse moves per 900ms drag. Playwright 1.63.0 takes one frame (about 16.6ms) per move instead of 8.4ms, so the drag overran its animation by about 90ms and the reviewer's 10% tolerance rejected it as non-smooth in 6 of 15 local runs (0 of 14 on 1.62.1).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all open issues, review adversarially with Codex until satisfied, then open and merge the PR.

## Acceptance + steps

- [x] SessionStart starts the update as a detached process in its own session, with no inherited pipes, and reports the last result → `test_start_detaches_worker_without_inherited_pipes`, `test_session_reports_update_status_without_running_update`.
- [x] A second session or `setup.sh` never starts a concurrent update → `test_running_update_is_reported_not_duplicated`.
- [x] Stop reports a running update instead of asking for another → `test_stop_waits_for_running_update_instead_of_rerunning_setup`.
- [x] Only candidates whose owning update exited are removed; running, legacy and scaffold-check candidates stay → `test_update_removes_only_candidates_whose_update_exited`.
- [x] `SIGTERM` stops every process of the update, including one that ignores SIGTERM, and records the failure → `test_interrupted_update_stops_every_process_and_records_failure`.
- [x] A failed update commit keeps an edit made while it ran, even one to a path already checked; an interruption after the commit keeps the update, even when the agent committed first, and reports it as installed → `test_failed_update_commit_keeps_edits_made_while_it_ran`, `test_rollback_keeps_an_edit_made_to_an_already_checked_path`, `test_interrupt_after_the_update_commit_keeps_the_update`, `test_update_commit_landing_after_an_agent_commit_is_kept`, `test_interrupt_after_installing_reports_the_installed_revision`.
- [x] The update commit is not counted as the session's work; later session edits and a user commit after the update still are → `test_update_commit_is_not_counted_as_session_work`.
- [x] Uninstalled checkouts still report why they cannot update, without a worker → `test_unavailable_update_is_reported_without_a_worker`.
- [x] An interrupted file write keeps the original file, and a failed update commit unstages only index entries still holding the updater's staging → `test_interrupted_write_keeps_the_original_file`, `test_failed_update_commit_keeps_staging_made_while_it_ran`.
- [x] Update and same-revision repair write each path only while it still holds the content the update planned from, roll back only paths they wrote, restore the index entries they replaced, and restore a retired skill link when the commit fails → `test_update_keeps_an_edit_made_before_it_reached_that_path`, `test_rollback_leaves_paths_the_update_never_reached`, `test_failed_update_commit_restores_staging_made_before_it`, `test_migrating_a_skill_link_keeps_a_file_created_during_it[update|repair]`, `test_failed_update_restores_the_skill_folder_link`.
- [x] A turn that changed nothing since the last passing check skips the rerun, a later edit or a failed check still runs it, and an interrupted Stop hook stops every check process → `test_unchanged_turn_after_a_passing_check_does_not_rerun_it`, `test_failed_check_is_rerun_on_the_next_turn`, `test_interrupted_stop_hook_stops_every_check_process`.
- [x] Both video skills pin `playwright` 1.63.0 with lockfiles regenerated by pnpm, and the walkthrough's drag keeps to its planned duration on 1.63.0, where each mouse move takes a whole frame → the skill's `pnpm test`.

## Baseline + execution

Result: Passed
Evidence: main `6eba8cb` passed the hard-eng workflow (run 36560306283). Issue 213 was reproduced from the code: `session_context` calls `update(root)` synchronously and `verify_candidate` runs the full check with `timeout=3500`.
Execution: One branch, one commit per issue.

## Risks + recovery

The update now commits while the agent may be working; it keeps its existing guards (clean update paths before and after verification, `git commit --only`) and rolls back only its own writes. Rollback rechecks each path after preparing its replacement, just before the rename; an edit landing between that check and the rename is a filesystem limit shared with `git checkout` and editors, since there is no portable compare-and-swap rename. A `SIGKILL` of the supervisor leaves the update running; the update keeps the lock until it exits. A `SIGKILL` of the update is cleaned up by the supervisor. Accepted limits, left unfixed as narrow edge cases: an agent edit landing in the few milliseconds between a path's recheck and its rename, between the final recheck and `git commit` reading the worktree, or a `chmod` of a planned script in that window; a SIGTERM between recording a path and writing it may report that one path as kept. Hook installation and legacy retirement behave as on main. Recovery is reverting this branch.

## ux_reference

N/A — hook messages and dependency pins only; no product appearance.

## Verification

Result: Passed
E2E: Passed — sandbox Python project installed from verified upstream `7eebdaf` with the real `setup.sh`. The branch's SessionStart hook returned in 0.49s with the update running in its own process group, and a second session reported it without starting another. A real `claude -p` session in that project finished in 10s while the update carried on and recorded its result. On a clean copy the detached runner updated to verified `6eba8cb` in about 90s, made the local commit, moved the session base to it and left no worktree. `SIGTERM` during candidate verification stopped every process in the group, removed the candidate and recorded "interrupted by signal 15". After a `SIGKILL`, the next run removed the leaked candidate and its temporary directory, then completed the update.
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates at `93d9744a` (1118 tests). Codex adversarial review ran 12 rounds; every finding reachable in normal use was fixed with a regression that failed first, and the remaining narrow races are listed under Risks. Further sandbox runs on copies of the installed project: a failed update commit and a failed legacy skill-link migration both left a clean tree and index and restored the link; successful updates and a legacy migration moved the session base to the update commit; `SIGTERM` during cleanup with a TERM-ignoring descendant killed it before the lock was released; `SIGKILL` of the supervisor let the update keep the lock and finish, and `SIGKILL` of the update was recorded as "update exited -9". The real Stop hook in this repository ran the full check on a session change (180 s, passed), skipped it on the next unchanged turn (under 1 s) and ran it again after an edit (135 s, passed). Playwright 1.63.0: the walkthrough skill's `pnpm test` passed 16/16 with drag windows of 917–937 ms (unpaced 1.63.0 took about 992 ms and failed 6 of 15), and the marketing-video render calls (route, goto, evaluate, screenshot) ran cleanly from its frozen lockfile.

Delivery target: Merge
Delivery: Pending — PR checks, squash merge and main CI.
