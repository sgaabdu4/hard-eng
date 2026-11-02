# Revert the interrupt handling added to run_in_group

Status: Complete

## Outcome + scope

Main's push CI is green again. Two commits from the narrow challenge PR changed `run_in_group` in `.hooks/process_group.py`: they swapped the host's SIGINT, SIGTERM and SIGHUP handlers while a command started, and blocked those signals while the handlers were put back. Both commits are reverted. The `challenge.py` coverage work from the same PR stays. Non-goals: a new fix for the start gap (see Risks).

## Repository context

Owners: `run_in_group` in `.hooks/process_group.py`; its tests in `tests/test_process_group.py`.
Cause: a Python signal handler runs in the main thread at the next bytecode, whichever thread receives the signal. So a main-thread mask cannot defer it, and a handler restore loop cannot be atomic. On main run 41516271199 the restore test's handler raised inside the loop, after the mask was set. That left SIGINT and SIGTERM blocked in that pytest worker, and the worker's later children inherited the mask and ignored SIGTERM.
Same cause: only `run_in_group` changed signal handlers or masks in those commits.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the weekly reference repo watch task authorizes PRs into `develop` and the release to `main`; a red `main` caused by this run must be repaired in this run.
Decided: revert, do not fix forward. A sound fix needs its own review cycle.

## Acceptance + steps

- [x] `run_in_group` and its tests match `develop` before the reverted commits → N/A — a revert, proved by an empty `git diff 8e666dce HEAD -- .hooks/process_group.py tests/test_process_group.py`.
- [x] The tests that hung on main pass again → `tests/test_ship_actions.py::test_interrupted_pre_push_removes_its_snapshot`, `tests/test_update_runner.py::test_interrupted_update_stops_every_process_and_records_failure`.

Removed test: tests/test_process_group.py :: test_an_interrupt_while_a_command_starts_stops_that_command :: it proved the reverted handler swap; that behavior is gone and the start gap is open again (see Risks).
Removed test: tests/test_process_group.py :: test_an_interrupt_while_handlers_are_restored_stops_the_command :: it proved the reverted signal mask, which is the cause of the red main run; that behavior is gone.

## Baseline + execution

Result: Passed
Evidence: main run 41516271199 failed in `tests/test_process_group.py::test_an_interrupt_while_handlers_are_restored_stops_the_command` (SIGTERM still on the recorder lambda), then `test_interrupted_pre_push_removes_its_snapshot[15]` and `test_interrupted_update_stops_every_process_and_records_failure[during-update]` timed out in the same worker.
Execution: One builder, this session. Two `git revert` commits, newest first.

## Risks + recovery

Open gap, not fixed: an interrupt that lands inside `Popen`, or before `run_in_group` enters its `try`, leaves the started command running. It shows up only under heavy load, for example in `tests/test_mutation.py::test_interrupted_mutation_stops_the_tool_it_started`. A sound direction for a later PR is to start the command from a helper thread, where Python handlers never run, and let the main thread join and clean up. Recovery: revert these two revert commits to restore the reverted code.

## ux_reference

N/A — hook behavior with no visual surface.

## Verification

Result: Passed
Evidence: focused tests in `tests/test_process_group.py`, `tests/test_mutation.py`, `tests/test_ship_actions.py` and `tests/test_update_runner.py` pass. The pre-push gate runs the full suite on this commit.
E2E: N/A — hook internals; main's push CI is the proof.

Delivery target: Merge
Delivery: Pending — PR into `develop`, then a release to `main` with main's push CI green.
