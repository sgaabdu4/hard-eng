# Freshness waits for pub upgrades blocked by a young release

Status: Complete

## Outcome + scope

The Dart and Flutter freshness check reads `pub outdated --json` and takes the "resolvable" version. Pub works that out as if every other package could also move to its newest release, even one under 2 days old. So a package can be reported stale while its printed upgrade fails: a pinned package must move to a release that is not 2 days old yet, and no project change can pass. Now each stale Dart or Flutter package gets one `<tool> pub upgrade --major-versions <name> --dry-run`. When it fails to resolve and every exact version it names has only fixes younger than the wait, the release is named as waiting and does not fail the check. Any other failure, or a due fix, keeps the package failing. Non-goals: other package managers, the wait length.

## Repository context

Owners: `.hooks/freshness.py` (freshness rules), `.hooks/reports.py` (picks the waiting check per tool).
Same cause: as with Bun, the check and the upgrade it prints used different age rules.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "OMG why wait 15 hours from now... this is an issue with hard-eng now then?" after the earlier Bun fix of the same kind; merge after green checks.
Decision: the dry run runs only for packages already found stale, so a current project runs no extra command.

## Acceptance + steps

- [x] A stale pub package whose upgrade only a young release can unblock is named as waiting and does not fail → `tests/test_freshness.py::test_flutter_waits_while_only_a_young_release_unblocks_the_upgrade`.
- [x] Once the blocking fix is due, or when the upgrade resolves, the package fails as before → `tests/test_freshness.py::test_flutter_waits_while_only_a_young_release_unblocks_the_upgrade`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after the starter release; the new cases failed before the change.
Execution: one session; failing test first, the fix, the full check, PR, release.

## Risks + recovery

A dry run adds one resolve per stale pub package. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: freshness tests 32 passed; a real dry run on a real Flutter project marked a blocked release as waiting, a resolving one as not waiting, and changed no files; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey; the test runs the real check with a stand-in Flutter.
Delivery target: PR
Delivery: Pending — PR into develop.
