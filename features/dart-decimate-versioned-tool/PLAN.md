# Accept versioned Dart Decimate tool names

Status: Complete

## Outcome + scope

`validate_dart_decimate` accepts a report whose `tool` field is `dart-decimate` or `dart-decimate <version>` and keeps every other check exact, so Dart packages pass again with dart-decimate 0.0.44 and any later release. Nothing else is loosened; no other validator changes.

## Repository context

Owner: `.hooks/reports.py` `validate_dart_decimate`, which compared the report envelope, including `tool`, against exact values. dart-decimate 0.0.44 (released 17 September 2026) writes `"tool": "dart-decimate 0.0.44"`; 0.0.43 wrote `"tool": "dart-decimate"`, both confirmed on the same Flutter tree with the provisioned binaries. `tool_setup.provision_tools` installs `npm:dart-decimate@latest`, so the release failed every Dart package at once ("Expected a passing combined Dart Decimate check") with no repository change; the user reported it from a Flutter repository whose every report has the expected schema, kind, command, pass verdict, empty findings and zero counts. The only other tool-name comparison in `reports.py` is the Gitleaks SARIF driver name, which has not changed. Fixtures: `tests/test_reports.py` `REPORTS["dart-decimate"]` and the `test_findings_and_empty_analysis_fail` mutation table.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for this fix, the red/green test, the check of sibling validators, the gates and a PR with cause, fix and proof. The version part of the match is unpinned because provisioning always uses the latest release.

## Acceptance + steps

- [x] A passing report with `dart-decimate 0.0.44` (and a prerelease version) validates; a bare `dart-decimate` still validates → `test_dart_decimate_accepts_versioned_tool_name`, red before the fix.
- [x] A wrong tool name such as `other-tool 1.0.0` still fails → new row in `test_findings_and_empty_analysis_fail`.
- [x] Full check passes; the real 0.0.44 report from a Flutter tree is rejected by the old validator and accepted by the new one.

## Baseline + execution

Result: Passed
Evidence: main at e45b0cd, CI run 35221637420 success; local full check on that tree passed earlier today with 745 tests.
Execution: Single session in a worktree off main.

## Risks + recovery

A future release that changes the report schema again fails the same exact checks with the same message; the version suffix now accepted is `<digits>.<digits>.<digits>` plus an optional non-space tail. Recovery is reverting the one-line match.

## ux_reference

N/A — validator change.

## Verification

Result: Passed
Evidence: Red with `.hooks/reports.py` stashed: `test_dart_decimate_accepts_versioned_tool_name` failed for `dart-decimate 0.0.44` and `dart-decimate 0.1.0-beta.1` with "Expected a passing combined Dart Decimate check", while the bare name and the `other-tool 1.0.0` mutation row passed (2 failed, 2 passed). Green after: `tests/test_reports.py` 153 passed; ruff format and check clean. `reports.py` gained one line.
E2E: Passed — the provisioned dart-decimate 0.0.44 ran `check lib --threshold 0 --format json` on a client Flutter monorepo (verdict pass, tool `dart-decimate 0.0.44`); the unmodified validator rejected that file with "Expected a passing combined Dart Decimate check" and the fixed validator accepted it. The 0.0.43 binary on the same tree writes `"tool": "dart-decimate"`, which still validates.

Delivery target: PR
Delivery: Pending — full `hard-eng.py check --base origin/main` on the final tree passed: exit 0, 754 tests in 177 s, every native check passed (a first run in the fresh worktree failed only because its submodules were not yet initialised).
