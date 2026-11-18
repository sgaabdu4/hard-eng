# A gate keeps its time limit when the machine is busy

Status: Complete

## Outcome + scope

A gate limit follows the slowest of the last 5 passing times, and a gate that stopped at its limit gets the full budget on its next run. Non-goals: a load reading, a queue, a lock, a project setting, a larger floor.

## Sources + coverage

Sources: N/A — the request is the only source
Deliverables: None

## Repository context

Owners: `.hooks/gate_times.py` (`gate_limit`, the record functions) and `run_gate` in `.hooks/gate_runner.py`; the tests in `tests/test_gate_speed.py`.
Same cause: the cause is a limit that follows one sample. Searched `.hooks` for other readers of `hard-eng-gate-times.json` and for other limits made from a past time: `gate_limit` is the only one, and `shards.py` reads the limit only through `gate_limit`. No earlier fix of this cause. Both halves are fixed together: one fast pass shrank the limit of every worktree, and a stop at the limit recorded nothing.
Single source: the gate time file and its rules live only in `gate_times.py`; `run_gate` calls its record functions. The other `flock` calls in `.hooks` lock other files for other purposes (installs, one check for each checkout); none is a shared helper, so there is no second copy to merge. Searched `.hooks` and `tests` for the file name and for `GATE_FLOOR_SECONDS`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer decided the rule: the slowest of the last few passing times, three times that, a floor of 600 seconds, a cap at the budget, and the full budget after a stop at the limit.
Decisions:

1. The file keeps its name. A gate holds `{"passes": [...], "timed_out": bool}`. A file with one number for a gate, or a list, still loads, so a worktree on an older Hard Eng and one on this version can share the file; the older code treats the new form as no record and uses the budget.
2. A stop at the limit is the command timeout of the gate, carried from the runner by a set, not read from elapsed time, because preparation and each project run add to the elapsed time. The stop stays a failure after the debt judge. A gate that fails on a finding records nothing.
3. The file is locked across processes with `flock` on a lock file beside it, because worktrees share it. That lock replaces the thread lock.
4. The independent review gave 3 findings in 3 rounds, all repaired with a red test first: a stop passed by the debt judge, a lost update between processes, and a stop inferred from elapsed time. Round 4 found no fault in the code. The files were then split to stay under the file length limit; the later rounds found only faults in this plan's text, each repaired.
5. The lock is held only while the file is read and written, never while a gate runs. It is a kernel `flock` on an open file, so a killed process leaves nothing held. The wait is limited to 5 seconds; after that the record is skipped and the next limit stays as it was.
6. Old readers (the `main` hooks and the `hotfix/pre-push-ci-only` hooks) load the new file form without error and treat it as no record; an old write replaces the entry with one number, which the new code reads.

## Acceptance + steps

- [x] After passes of 900 s and then 180 s the limit is 2700 s, capped at the budget, not the floor → `tests/test_gate_limits.py::test_one_fast_pass_does_not_shrink_the_limit_below_a_slower_recent_pass`
- [x] Only the last 5 passing times set the limit → `tests/test_gate_limits.py::test_only_the_last_five_passing_times_set_the_limit`
- [x] After a stop at the limit the next limit is the full budget, and the next pass clears it → `tests/test_gate_limits.py::test_a_gate_that_timed_out_gets_the_full_budget_until_it_passes`
- [x] A real hung gate stops at its limit and the next run gets the full budget → `tests/test_gate_limits.py::test_a_gate_stopped_at_its_limit_gets_the_full_budget_next_time`
- [x] A stop at the limit stays a failure when the debt judge calls the gate a pass → `tests/test_gate_limits.py::test_a_stop_at_the_limit_fails_the_check_when_the_debt_judge_calls_the_gate_a_pass`
- [x] A slow start of a gate that did not time out records no stop → `tests/test_gate_limits.py::test_a_slow_start_is_not_a_stop_at_the_limit`
- [x] Two processes cannot lose each other's record → `tests/test_gate_limits.py::test_a_check_in_another_process_cannot_lose_a_record`
- [x] A record waits a limited time for the lock and is then skipped → `tests/test_gate_limits.py::test_a_record_waits_a_limited_time_for_the_lock_and_then_is_skipped`
- [x] A file with one number for each gate still loads → `tests/test_gate_limits.py::test_a_file_with_one_number_for_each_gate_still_loads`
- [x] A gate with no record gets the budget → `tests/test_gate_limits.py::test_a_gate_with_no_record_gets_the_budget`

## Baseline + execution

Result: Passed
Evidence: before the fix, the shrink test failed with 540 against 2700, the stop test with the missing record function, and the real hung gate test with 1 against 120; the other four cases passed.
Execution: one builder; red tests, the fix, the gates, the challenge, the Complete check.

## Risks + recovery

- A slow pass that comes from a busy machine raises the limit for 5 passes. That only lets a hung gate run longer, up to the budget.
- Recovery: revert the commit; the older code reads the new file as no record.

## ux_reference

N/A — no screen changes.

## Verification

Result: Passed
Evidence: `tests/test_gate_speed.py`, `tests/test_gate_limits.py` and `tests/test_shards.py` pass (149 tests). The static gates of `hard-eng.gates.json` for Python (format, lint, complexity, annotations, types, dead code) pass on the touched files. The independent review found 3 code faults in rounds 1 to 3, found none in round 4, and then found only plan text faults, each repaired. Not checked: a run against a real busy machine; the measured case of a project is covered by the first test, which uses its numbers.
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service.
Retro: (1) Escaped bug on the base branch: one fast pass shrank the limit of every worktree to the floor, and a stop recorded nothing, so a project's scan stopped at 600 s with no finding while it needs about 934 s under load. The gate that should have caught it is `tests/test_gate_speed.py`, which had one case for the limit; the new cases, now in `tests/test_gate_limits.py`, fail on the revision before the fix (540 against 2700, the missing record function, 1 against 120) and pass after → `tests/test_gate_limits.py::test_one_fast_pass_does_not_shrink_the_limit_below_a_slower_recent_pass`. (2) Three review findings in the first candidate → `tests/test_gate_limits.py::test_a_stop_at_the_limit_fails_the_check_when_the_debt_judge_calls_the_gate_a_pass`, `tests/test_gate_limits.py::test_a_check_in_another_process_cannot_lose_a_record` and `tests/test_gate_limits.py::test_a_slow_start_is_not_a_stop_at_the_limit`. (3) The stop that the debt judge turned into a pass is an escaped bug on the base branch as well: the test `tests/test_gate_limits.py::test_a_stop_at_the_limit_fails_the_check_when_the_debt_judge_calls_the_gate_a_pass` fails on the base revision (the check returned 0 with the judge stubbed to pass; a real gate that prints its recorded debt and then hangs was not run) and passes after. (4) A type check failure on a list type and on an untyped lambda, fixed before the first push → None — the type gate caught each in the focused run.

Delivery target: PR
Delivery: Pending — the pull request into `develop` and its checks.
