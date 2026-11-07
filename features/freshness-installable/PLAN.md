# Freshness waits for releases Bun cannot install yet

Status: Complete

## Outcome + scope

The Bun freshness check reads `bun outdated --minimum-release-age=172800`, which judges each direct package by its own release date. A package can pass the 2-day wait while a dependency it pins is still younger, so the printed `bun update --latest` fix fails with "blocked by minimum-release-age" and no project change can pass. Now each stale Bun package gets one `bun update --latest <name> --dry-run` with the same wait; a release blocked that way is named as waiting and does not fail the check, and it fails the check once installable. Any other dry-run failure keeps the package failing. Non-goals: other package managers, the wait length.

## Repository context

Owners: `.hooks/freshness.py` (freshness rules), `.hooks/reports.py` (passes the gate's directory).
Same cause: the check and the fix it prints used different age rules: the check looked only at the direct package, the install also at its pinned dependencies.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "yeah okay fucking update then" to fixing this freshness gap; merge after green checks.
Decision: the dry run runs only for packages already found stale, so a current project runs no extra command.

## Acceptance + steps

- [x] A stale Bun package whose dry run is blocked by the release age is named as waiting and does not fail the check; other stale packages still fail → `tests/test_freshness.py::test_gate_run_shows_the_tool_message_and_the_stale_package`.
- [x] A dry run that fails for any other reason keeps the package failing → `tests/test_freshness.py::test_gate_run_shows_the_tool_message_and_the_stale_package`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after the strict-checks release; the new cases failed before the change.
Execution: one session; failing tests first, the fix, the full check, PR, release.

## Risks + recovery

A dry run adds one network resolve per stale package. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: freshness tests 29 passed; real dry runs on a real project: a blocked release exits 1 with "blocked by minimum-release-age", an installable one exits 0, and neither changes files; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey; the gate test runs the real gate with a stand-in Bun.
Delivery target: PR
Delivery: Pending — PR into develop.
