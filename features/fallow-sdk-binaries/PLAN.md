# Fallow takes required SDK commands as provided

Status: Complete

## Outcome + scope

fallow 3.40.0 reports an unlisted binary for any command that no installed package provides. In a polyglot repository, JavaScript tests can run `dart` or `flutter`, which the Dart SDK provides and no npm package can. Fallow's only fixes are a dev package, which cannot exist, or an `ignoreBinaries` list, which Hard Eng bans. So the dead-code gate fails and no project change can pass. Now, when the repository tracks a `pubspec.yaml`, Hard Eng takes `dart` and `flutter` as provided while it reads the fallow report, names them in the output, and judges the rest of the report as before. Any other unlisted binary still fails. Non-goals: other SDKs, fallow config changes.

## Repository context

Owners: `.hooks/fallow_report.py` (fallow report rules), `.hooks/reports.py` (passes the package directory).
Same cause: the dead-code rule cannot see SDKs the repository already requires.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07, through a project coordinator, asked Hard Eng to treat toolchain commands it requires as known when it reads fallow; merge after green checks.
Decision: detect the SDK from a tracked `pubspec.yaml`, the same file Hard Eng uses to find Dart packages; no project list.

## Acceptance + steps

- [x] An audit whose only finding is an unlisted `dart` passes in a repository with a `pubspec.yaml`, and fails without one → `tests/test_fallow_sdk.py::test_fallow_takes_the_dart_sdk_as_provided_only_in_a_dart_repository`.
- [x] Another unlisted binary beside it still fails → `tests/test_fallow_sdk.py::test_fallow_takes_the_dart_sdk_as_provided_only_in_a_dart_repository`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after the pub freshness release; the new test failed before the change.
Execution: one session; failing test first, the fix, the full check, PR, release.

## Risks + recovery

A repository with a `pubspec.yaml` but no Dart SDK on the runner would pass the report and fail later when the test runs `dart`. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: fallow report tests 38 passed, using a report recorded from fallow 3.40.0; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey.
Delivery target: PR
Delivery: Pending — PR into develop.
