# Reuse multiple verified coverage owners before Fallow

Status: Complete

## Outcome + scope

Allow a standalone Fallow command to prepare its own package coverage plus an
explicitly configured dependent package coverage report, while the native gate
reuses those serial reports and runs only the Fallow scan. Preserve native
reports, CRAP enforcement and rejection of arbitrary, reordered or parallel
commands. No new runner, dependency or fallback is needed.

## Repository context

The existing resolver accepts exactly one preceding package test command before
a scan alias. A root Fallow audit can legitimately consume more than one
declared coverage owner. Its self-contained standalone command therefore fails
the exact-one resolver even when native dependency ordering already produces
the same reports.

## Decisions + authorization

Blockers: None
The user authorized this minimal resolver repair and its release. Limit the
change to the existing Fallow owner and existing report tests.

## Baseline + execution

Result: Passed
Evidence: Verified source main `48abaf8` has delivered CI. The failing target
configuration reproduces the exact resolver boundary; no command was executed
by that configuration failure.

## Acceptance + steps

- [x] Accept only a serial standalone chain of declared nonparallel coverage
  owners followed by the configured native scan alias.
- [x] Reject missing, reordered, parallel, duplicated or unrelated commands.
- [x] Retain managed scanner selection and native Fallow report validation.
- [x] Run focused source regressions before the final source gate and Merge
  delivery.

## Risks + recovery

Permitting arbitrary prerequisites could hide stale or unrelated coverage.
Compare every preceding command exactly against declared tests gates in their
configured serial order, and retain the current scan/report checks. Revert this
small owner change if the negative cases fail.

## ux_reference

N/A — this is command validation without product UI.

## Verification

Result: Passed
Evidence: The focused report and affected-selection suite passed 220 tests. It
accepts the serial sibling-package chain and rejects an extra command, a wrong
relative directory, either missing dependency edge, owner-after-consumer
ordering and parallel coverage. The changed-path test shows a consumer-only
change selects its coverage owner only with the reverse declared edge. Lint
and the provisioned type checker passed. The final Complete gate passed 676
tests in 140.61 seconds with 88.31% line coverage and all configured scanner,
security and performance checks. Delivery remains required.
E2E: N/A — the native subprocess report fixture is the relevant runtime
boundary.

Delivery target: Merge
Delivery: Pending
