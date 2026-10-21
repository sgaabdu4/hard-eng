# OSV failure findings

Status: Complete

## Outcome + scope

When the vulnerabilities gate fails, its output names each vulnerable package with its advisory IDs. Before, OSV wrote its findings only to the report file, Hard Eng read that file only after a pass, and the log showed only scan progress. Non-goals: other scanners and the pass rules.

## Repository context

Owners: `run_gate` in `.hooks/hard-eng.py` reads scanner reports; `validate_osv_package` in `.hooks/reports.py` builds the OSV error. Found in the 2026-10-20 timing run on installed projects: one project's vulnerabilities gate failed with no reason in its log.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 to look into the failing checks from the timing run. Decided: after a failed OSV run, read its report and print the validation error; the gate still fails.

## Acceptance + steps

- [x] A failed OSV run prints the vulnerable package and its advisory IDs, and the gate fails → `tests/test_greenfield.py::test_failed_vulnerability_scan_names_the_vulnerable_packages`.

## Baseline + execution

Result: Passed
Evidence: `develop` eb88231: the new test failed; the output held only the scan progress line and the FAIL line.
Execution: One builder; failing test first, then the report read after a failed run.

## Risks + recovery

A malformed report after a failed run prints its validation error; the gate fails either way. Revert the `elif` block in `run_gate` to restore the old output.

## ux_reference

N/A — gate output with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1,857 passed; the same 6 environment failures as `develop` (no Dart or Swift in this container). Ruff format and lint pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the test runs the real gate against a stand-in scanner that writes a real report shape.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
