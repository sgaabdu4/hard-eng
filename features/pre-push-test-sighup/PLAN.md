# Start the pre-push interrupt test with the default SIGHUP

Status: Complete

## Outcome + scope

`tests/test_ship_actions.py::test_interrupted_pre_push_removes_its_snapshot` gives the same result whether or not the process that runs the tests ignores SIGHUP. Non-goals: the pre-push hook itself and its signal handling.

## Sources + coverage

Sources: N/A — the request is a test that failed in full runs on three branches that do not touch it; no user source.

## Repository context

Owners: `tests/test_ship_actions.py` (the test) and `.hooks/ship_actions.py` (the hook it starts, unchanged).
Same cause: N/A — no earlier fix of this cause. Searched the tests for `SIGHUP` and `Popen(` of `hard-eng.py`: this is the only test that sends a hook SIGHUP and waits for it to stop.
Single source: N/A — no value gains a second copy.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — baseline repair. The failure blocks the Complete check of the open strict-rules branches.

## Acceptance + steps

- [x] The SIGHUP case passes when the runner ignores SIGHUP → `tests/test_ship_actions.py::test_interrupted_pre_push_removes_its_snapshot`: under `perl -e '$SIG{HUP}="IGNORE"; exec @ARGV'` it gave `1 failed, 1 passed` before the change (`[1]` timed out after 30 seconds) and `2 passed` after it.
- [x] The SIGTERM case still passes → the `[15]` case of the same test passes before and after.

## Baseline + execution

Result: Passed
Evidence: 2026-11-18, develop 5eaf31b7: the `Hard Eng` and `Canary` workflows passed on the push. The failed baseline of this behavior: full suites on three strict-rules branches failed only this case, with a 30 second timeout; it passes alone with the default SIGHUP.
Execution: One builder, this session.

## Risks + recovery

N/A — one test line; a revert restores it.

## ux_reference

N/A — tests only; no visible UI.

## Verification

Result: Passed
Evidence: the test under an ignored SIGHUP: `2 passed` after the change, `1 failed, 1 passed` before it.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) Escaped bug: the `pre-push` child keeps an inherited ignored SIGHUP, and the test assumed it was not ignored, so it passed every gate on runners that leave SIGHUP at the default → the gate that should have caught it is `tests`, and the acceptance line above is the run under an ignored SIGHUP that fails on the base revision. The test now starts the hook through a one-line wrapper that resets SIGHUP to the default. (2) The push refused the change without a plan, because it removes a line from a test file → None — the refusal named the step.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
