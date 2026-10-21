# Fallow empty audit

Status: Complete

## Outcome + scope

A `fallow audit` report for a change with no changed files passes when its verdict is pass and its summary counts are zero. Before, the check failed with "Fallow report is incomplete", because Fallow 3.34.1 then leaves out its dead-code, duplication and complexity sections. Non-goals: reports that hold those sections, and the combined `fallow` report.

## Repository context

Owners: `validate_fallow` in `.hooks/fallow_report.py` reads the three sections of an audit report without a check that they exist. Found in the 2026-10-20 timing run on installed projects: one project's full check failed on this error with no changed files since its base.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 to look into the failing checks from the timing run. Decided: accept the short report only when `changed_files_count` is the integer 0 and none of the three sections is present, so a report with sections stays fully checked.

## Acceptance + steps

- [x] An audit of no changed files with a pass verdict and zero counts passes; a count of 1, a fail verdict or a non-zero summary count fails → `tests/test_reports.py::test_fallow_audit_of_no_changed_files_passes_only_when_empty`.
- [x] A full audit report still needs active CRAP enforcement → `tests/test_reports.py::test_fallow_audit_requires_active_crap_enforcement`.

## Baseline + execution

Result: Passed
Evidence: `develop` b49978d: the new test failed with "Fallow report is incomplete". A real Fallow 3.34.1 audit with no changed files now passes, and an audit with a new unused export still fails.
Execution: One builder; failing test first, then the check in `validate_fallow`.

## Risks + recovery

A future Fallow that drops the sections for another reason still needs `changed_files_count` 0 to pass. Revert `empty_audit` to restore the old result.

## ux_reference

N/A — report validation with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1,856 passed; the same 6 environment failures as `develop` (no Dart or Swift in this container). Ruff format and lint pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the test feeds the real report shape to the validator.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
