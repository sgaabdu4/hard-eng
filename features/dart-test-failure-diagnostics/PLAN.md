# Dart test failure diagnostics

Status: Complete

## Outcome + scope

When a configured Dart test gate exits nonzero, show one bounded failing-test name and error from its existing machine-format report before candidate cleanup. Successful runs remain quiet. This does not change gate selection, exit status, test execution, coverage requirements, or application repositories.

## Repository context

`.hooks/hard-eng.py` owns native gate execution and already captures Dart machine output into the configured test report. `.hooks/reports.py` owns report parsing and completion validation, but previously exposed no failing-test context when a candidate gate failed.

## Decisions + authorization

Blockers: None

The user authorized this minimal canonical observability repair. It parses only the existing machine report, normalizes one error to at most 300 characters, and emits it only after a nonzero Dart tests command. It does not dump reports or add data collection.

## Acceptance + steps

- [x] Reuse the Dart machine-report parser to identify the first failed test and its associated error.
- [x] Print that concise context before candidate cleanup only for a nonzero Dart tests command.
- [x] Preserve a quiet successful run and the original failing gate result.
- [x] Prove both paths with actual `dart test --reporter json` processes in a disposable generic package.

## Baseline + execution

Result: Passed
Evidence: The a8 updater candidate failed a root Dart tests gate with no test identity in its retained output. A clean a8 source worktree separately reproduces an unrelated existing `test_pre_push_tests_committed_code` failure, so that baseline failure is not attributed to this repair.

## Risks + recovery

Malformed, missing, or incomplete reports yield no added diagnostic and retain the existing gate failure. The parser emits only the first failed event and truncates the normalized error. Revert the task-owned parser and runner wiring if a supported machine format changes.

## ux_reference

N/A — native gate diagnostics have no product interface.

## Verification

Result: Passed
Evidence: `235 passed, 1 deselected` in the focused reports/runner suite; Ruff check and formatting passed. A disposable package invoked the real `dart test --reporter json` path: its failing assertion produced `Dart test failure: reports a real failing Dart assertion: Expected: <2> Actual: <1>` and retained `FAIL tests (exit 1)`. Its successful assertion emitted no failure summary and passed with exit 0 and 100% synthetic LCOV.
E2E: Passed — the disposable package exercised the same native `run_gate` subprocess/report/candidate-cleanup path used by a Dart tests gate; it used no consumer data or identifiers.

Delivery target: Merge
