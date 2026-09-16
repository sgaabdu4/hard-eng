# Dart typing scope reconciliation

Status: Complete

## Outcome + scope

Reconcile an existing root Dart analyzer gate with the template’s strict gate when both cover the package’s declared sources and authored test roots. Keep independently owned Dart packages on their existing `.` analyzer scope.

## Repository context

`setup.py:configure_typing_checks` compares existing native commands with template commands during setup and update. The Dart template uses `.`, while a root Flutter package may already use an explicit authored scope.

## Decisions + authorization

Blockers: None

The user authorized this focused canonical baseline repair after a supported consumer update preserved an exact failing test identity. No warning suppression, analyzer relaxation, or cross-package scope is introduced.

## Acceptance + steps

- [x] Expand only root Dart template type scopes to declared sources and existing authored test roots.
- [x] Reuse matching root checks instead of adding a duplicate strict check.
- [x] Retain nested Dart package `.` scopes.

## Baseline + execution

Result: Passed
Evidence: A real supported update candidate failed only because a duplicate root strict-types gate retained `dart analyze --fatal-infos .`; all other candidate checks passed.

## Risks + recovery

Only existing root test directories are included. Revert the setup reconciliation and regression if a supported root layout needs a different owner boundary.

## ux_reference

N/A — native setup behavior has no product interface.

## Verification

Result: Passed
Evidence: Focused setup tests passed with Ruff, formatting, Pyrefly, and whitespace checks.
E2E: Passed — the source regression exercises the same setup reconciliation used by an updater candidate.

Delivery target: Merge
