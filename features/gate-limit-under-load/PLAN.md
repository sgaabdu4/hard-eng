# A gate keeps its time limit when the machine is busy

Status: Draft

## Outcome + scope

A gate limit follows the slowest of the last 5 passing times, and a gate that stopped at its limit gets the full budget on its next run. Non-goals: a load reading, a queue, a lock, a project setting, a larger floor.

## Sources + coverage

Sources: N/A — the request is the only source
Deliverables: None

## Repository context

Owners: `.hooks/gate_times.py` (`gate_limit`, the record functions) and `run_gate` in `.hooks/gate_runner.py`; the tests in `tests/test_gate_speed.py`.
Same cause: the cause is a limit that follows one sample. Searched `.hooks` for other readers of `hard-eng-gate-times.json` and for other limits made from a past time: `gate_limit` is the only one, and `shards.py` reads the limit only through `gate_limit`. No earlier fix of this cause. Both halves are fixed together: one fast pass shrank the limit of every worktree, and a stop at the limit recorded nothing.
Single source: the gate time file and its rules live only in `gate_times.py`; `run_gate` calls its two record functions. Searched `.hooks` and `tests` for the file name and for `GATE_FLOOR_SECONDS`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer decided the rule: the slowest of the last few passing times, three times that, a floor of 600 seconds, a cap at the budget, and the full budget after a stop at the limit.
Decisions:

1. The file keeps its name. A gate holds `{"passes": [...], "timed_out": bool}`. A file with one number for a gate, or a list, still loads, so a worktree on an older Hard Eng and one on this version can share the file; the older code treats the new form as no record and uses the budget.
2. A stop at the limit is a failed gate whose run reached its limit. A gate that fails on a finding before its limit records nothing.

## Acceptance + steps

- [ ] After passes of 900 s and then 180 s the limit is 2700 s, capped at the budget, not the floor → `tests/test_gate_speed.py::test_one_fast_pass_does_not_shrink_the_limit_below_a_slower_recent_pass`
- [ ] Only the last 5 passing times set the limit → `tests/test_gate_speed.py::test_only_the_last_five_passing_times_set_the_limit`
- [ ] After a stop at the limit the next limit is the full budget, and the next pass clears it → `tests/test_gate_speed.py::test_a_gate_that_timed_out_gets_the_full_budget_until_it_passes`
- [ ] A real hung gate stops at its limit and the next run gets the full budget → `tests/test_gate_speed.py::test_a_gate_stopped_at_its_limit_gets_the_full_budget_next_time`
- [ ] A file with one number for each gate still loads → `tests/test_gate_speed.py::test_a_file_with_one_number_for_each_gate_still_loads`
- [ ] A gate with no record gets the budget → `tests/test_gate_speed.py::test_a_gate_with_no_record_gets_the_budget`

## Baseline + execution

Result: Pending
Evidence: before the fix, the shrink test failed with 540 against 2700, the stop test with the missing record function, and the real hung gate test with 1 against 120; the other four cases passed.
Execution: one builder; red tests, the fix, the gates, the challenge, the Complete check.

## Risks + recovery

- A slow pass that comes from a busy machine raises the limit for 5 passes. That only lets a hung gate run longer, up to the budget.
- Recovery: revert the commit; the older code reads the new file as no record.

## ux_reference

N/A — no screen changes.

## Verification

Result: Pending
Evidence: pending
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service.
Retro: pending

Delivery target: PR
Delivery: Pending — the pull request into `develop` and its checks.
