# Reuse verified coverage before a delegated Fallow scan

Status: Complete

## Outcome + scope

Allow a package's standalone check:fallow script to delegate to its scan-only script when the identical coverage/test command already runs earlier in the same gate group. Preserve native Fallow reports, metrics and the standalone command's coverage generation. Update the existing source CI cache action to its verified current release. No custom argument parser, new runner or persisted execution state.

## Repository context

The package service validator currently accepts only the exact check:fallow command name. The existing package-script resolver and native Fallow report validator already support delegated scripts; the command-name requirement prevents using them to avoid repeated coverage work.

The existing cache action used v5. The official actions/cache latest release and Git tag resolve v6.1.0 to 55cc8345863c7cc4c66a329aec7e433d2d1c52a9; retain the existing cache paths, keys and latest-tool resolution policy.

## Decisions + authorization

Blockers: None
The user authorized CI efficiency repairs and guarded delivery. Change the existing Fallow owner, package-service validator and tool-execution regression suite. Reuse native package scripts and ordered test gates.

## Baseline + execution

Result: Passed
Evidence: Source main 77776e8 has successful hard-eng CI. Its runtime code and configuration match the committed README pre-push proof, which passed all checks in 150.63 seconds. This change starts from that verified code; the existing audit-ownership regression also remains required.
One builder owns the small shared-tooling repair. Consumer acceptance runs independently.

## Acceptance + steps

- [x] A standalone script that runs the configured test command and then delegates to the configured scan is accepted without rerunning coverage in that scan.
- [x] Missing, reordered, parallel or different coverage prerequisites remain rejected.
- [x] An unrelated scan cannot replace the package's existing Fallow audit.
- [x] Native managed scanner selection and report validation remain active.
- [x] Focused regressions and full local gates pass; hosted CI is required for delivery.

## Risks + recovery

Accepting an arbitrary alias could skip a package audit or use stale coverage. Require an exact standalone command chain, a preceding nonparallel test owner, a nonparallel scan and the existing native Fallow report. Revert this scoped change if that contract cannot be demonstrated.

## ux_reference

N/A — command validation changes no product UI.

## Verification

Result: Passed
Evidence: The scanner/report and tool-execution regression suites passed 185 tests, including actual delegated subprocess execution with a stale local binary present. Pyrefly reports zero errors. The full source Ready gate passed all checks. The final Complete gate and hosted shipping proof remain required before delivery.
E2E: Passed — the delegated command ran through the actual managed scanner subprocess fixture with a stale local binary present. Native report validation stayed active. Consumer rollout is tracked separately.

Delivery target: Merge
Delivery: Pending
