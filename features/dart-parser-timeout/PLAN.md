# Give the Dart declaration parser time to finish under load

Status: Complete

## Outcome + scope

Baseline repair: `erased_dart` gives the Dart declaration parser 300 seconds instead of 60, so declaration-only files stay out of coverage when the machine is busy. Before, a timeout silently waived nothing and the coverage gate failed falsely. Non-goals: caching a compiled parser or changing which files are erased.

## Repository context

Owners: `erased_dart` in `.hooks/dart_coverage.py`, called from `line_coverage` in `.hooks/reports.py`. Each call JIT-compiles `package:analyzer`: 17–22 s alone on a 16-core machine, about 88 s with 12 concurrent calls. The full gate on unchanged `ba19011` failed `tests/test_dart_coverage.py::test_native_dart_declarations_and_runtime_controls` with an empty erased set; the test passes alone.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix all Hard Eng issues and merge to main through a PR; this repair precedes that work under the baseline-repair rule.

## Acceptance + steps

- [x] 12 concurrent `erased_dart` calls on the test fixture → each returns all 6 declaration-only files.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `ba19011` → 16/17 gates PASS; `tests` failed 1 of 800 on the Dart declaration test. 12 concurrent `erased_dart` calls → all hit the 60 s timeout and returned 0 files.
Execution: One builder; raise the timeout at its single call site.

## Risks + recovery

A hung parser now blocks coverage validation for up to 300 s instead of 60; it still fails safe by waiving nothing. Lower the value if a project's budget needs it.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: 12 concurrent `erased_dart` calls with the 300 s timeout → each returned 6 files in about 78 s. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 800 tests passed.
E2E: N/A — hook timeout change; the concurrent parser run exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
