# A coverage reader is blocked, not failed, when its tests fail

Status: Complete

## Outcome + scope

When a test gate fails, the Fallow gate that reads its coverage no longer runs and fails on a missing coverage file. It prints `BLOCKED <gate>: it reads the coverage of <package>/<tests>, which failed`. The check still fails, and only the test gate counts as a failed gate. Non-goals: other gate order, the quick check, hook time.

## Repository context

Owners: `.hooks/gate_schedule.py` (`run_checks`, `reads_coverage`), `tests/test_gate_speed.py`.
Evidence: in a consumer's push gate logs, one failed web test suite also failed Fallow with "coverage: failed to read coverage file … coverage-final.json: No such file or directory", so one break showed as two or three failed checks, and repeat counts grew for the wrong gate. Fallow cannot run its audit without that file, so it gives no findings in this case.
Same cause: Fallow is the only gate that reads another gate's output (`reads_coverage`); no other gate waits on a test gate's files. The repeated lint failure in this change was `run_checks` crossing the complexity limit; the blocked case lives in `start` and `blocked_by` instead.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-11-08 to apply HE Learn to the consumer's late failures and fix Hard Eng without weakening any check.

## Acceptance + steps

- [x] A failed test gate blocks the Fallow gate that reads its coverage; Fallow does not run, the check fails, and only the test gate is a failed gate; other gates still run → `tests/test_gate_speed.py::test_a_coverage_reader_is_blocked_not_failed_when_its_tests_fail`.
- [x] Fallow still waits only for the test gates whose coverage it reads → `tests/test_gate_speed.py::test_a_gate_waits_only_for_gates_that_can_disturb_it`.

## Baseline + execution

Result: Passed
Evidence: develop 921d8ce8 passed required CI; this branch passed the full pre-push check on 2026-11-08 before this change.
Execution: This session, one builder, in the open staging PR at the maintainer's request.

## Risks + recovery

- A Fallow finding unrelated to coverage shows only after the tests pass. Fallow already could not run in this case. Recovery: revert the commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: On 2026-11-08 `uv run pytest -q tests/test_gate_speed.py`: 18 passed; the new test failed before the change with "verification failed in web/fallow, web/tests".
E2E: N/A — gate output with no user journey.
Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
