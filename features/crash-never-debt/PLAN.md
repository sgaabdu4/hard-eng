# A check that could not run never passes as debt

Status: Complete

## Outcome + scope

A gate that could not run (missing module or tool, or a time-out) or whose report cannot be read is never recorded as adoption debt and never passes as debt. Non-goals: which roles are recordable, the debt file format, and findings a gate reports through `ValueError`, such as `HE-PERFORMANCE-SUITE`, which still become debt.

## Repository context

Owners: `run_gate` in `.hooks/hard-eng.py` catches a gate's exception and passes its text to `remember` (`.hooks/debt.py`), which keeps it as the gate's output. `record` saves that output as debt, and `judge` compares later output with it. `fingerprints` turns a report it cannot parse into the line `unreadable report`.
Cause (seen on 2026-11-02 while testing the release canary's brownfield snapshot, pallets/itsdangerous 672971d): `adopt` recorded `No module named 'yaml'` as zizmor's debt. On develop b24b9fa, a gate whose tool does not exist fails during adoption with `[Errno 2] No such file or directory`, that line becomes debt, and the next run prints `DEBT lint: the failure above holds only the 1 lines recorded` and passes. A gate that times out the same way at adoption and later passes the same way.
Same cause: the PR that makes `adopt` restart with PyYAML removes one trigger (helped); this change removes the false pass for every trigger. Searched every `remember` caller (gate output and the exception path) and every line `fingerprints` adds: the exception path and `unreadable report` are the two places where a result the gate never produced becomes debt. Both are fixed here.
Escaped bug: the test gate should have caught it. Both new tests fail on develop b24b9fa: the false pass returns `False` where `True` is expected, and an unreadable report is recorded with exit 0 where 1 is expected.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the maintainer asked for every release check to be tested and gave full authority to fix what fails.
Decided: `ImportError`, `OSError` and `subprocess.TimeoutExpired` mean the gate could not run; their text is printed but not kept as output. `record` refuses a failed gate with no recordable line or with `unreadable report`, through the existing "must pass before adoption" path. A later adoption still only drops lines, as before.

## Acceptance + steps

- [x] A gate that cannot run is refused by adoption and fails the next run → `tests/test_debt.py::test_a_gate_that_cannot_run_is_never_passed_as_debt`.
- [x] An unreadable report is refused by adoption → `tests/test_debt.py::test_an_unreadable_report_is_never_recorded_as_debt`.
- [x] Old findings in a gate's output still become debt → `tests/test_debt.py::test_old_findings_pass_new_ones_fail_and_fixed_ones_must_be_dropped`.

## Baseline + execution

Result: Passed
Evidence: on develop b24b9fa the first new test failed with `assert False is True` after `DEBT lint: the failure above holds only the 1 lines recorded`; the second failed with `assert 0 == 1`.
Execution: One builder, this session. Failing test, then the exception path in `run_gate` and the refusal in `record`; then the second failing test and the `unreadable report` refusal.

## Risks + recovery

A first adoption now stops when a gate cannot run or fails with no recordable line, instead of skipping that gate; the next `check` failed on that gate anyway. Revert the commit to restore the old recording.

## ux_reference

N/A — command behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_debt.py` and `tests/test_adoption.py`: 73 passed. Brownfield proof on this branch: the release canary's `install_new` for the itsdangerous snapshot recorded the same 12 gates, including `performance` from its `HE-PERFORMANCE-SUITE` error, and a full `check` in that project exited 0.
E2E: Passed — the brownfield proof above runs the real install, `adopt` and `check` commands on the public snapshot.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
