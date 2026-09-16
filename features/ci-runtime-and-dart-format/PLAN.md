# Provision managed runtimes and format authored Dart

Status: Complete

## Outcome + scope

Existing CI jobs can provision the `uv` runtime required by selected managed
Python scanners through the existing local Mise owner. Dart setup discovers
authored package files at each format run, including platform and test files,
without traversing generated build output. Strict Dart analysis accepts the
platform exclusions Flutter itself adds only where every matched Dart file is
generated or vendored. This does not change documented shell
prerequisites for a Python environment missing YAML.

## Repository context

Managed scanner commands are normalized to `uvx`, while the runner checks for
YAML before gate provisioning. The Dart template previously formatted `.`;
its runtime Git inventory must keep discovering authored files added after
setup without walking generated output or masking inventory failures. Flutter
can add exclusions for existing platform directories during dependency setup,
so validation must retain authored Dart analysis.

## Decisions + authorization

Blockers: None
Authorized repair. Reuse the existing Mise provisioner and formatter command;
do not add a workflow, global installation, formatter framework, or broad
exclusion.

## Baseline + execution

Result: Passed
Evidence: A cold temporary PATH without `uv` installed `uv@latest` into the
provisioner's temporary Mise storage for a selected managed scanner. A native
Dart fixture proved generated build files are omitted while every authored
format root is checked.

## Acceptance + steps

- [x] Provision `uv` only when a selected managed Python scanner needs it.
- [x] Keep the pre-provision YAML runtime boundary explicit.
- [x] Discover authored Dart production, platform, unit, integration, and
  driver files at format time.
- [x] Exclude generated build and tool output from the formatter inputs.
- [x] Reject failed formatter inventory and ignore only deleted or empty inputs.
- [x] Permit existing Flutter platform exclusions only without authored Dart.
- [x] Cover positive and test-only adaptation paths with focused regressions.

## Risks + recovery

Installing an unrelated runtime adds avoidable work, so only normalized
managed-scanner commands select `uv`. Formatting generated output would create
noise; the formatter inventories Git-owned and unignored authored paths at
each run, then excludes generated and tool roots. Platform exclusions would
hide analysis if they covered authored Dart, so validation inspects tracked and
untracked paths before allowing them. Revert this small template and
provisioner change if either selection rule regresses.

## ux_reference

N/A — runtime setup and source formatting have no product interface.

## Verification

Result: Passed
Evidence: The all-up Ready gate passed 687 tests and the focused provisioner,
formatter, and Dart exclusion contracts passed 73/73. The real cold provisioner
receipt selected `uv@latest` with no `uv` on
PATH, exposed the temporary Mise executable, then executed `uvx` for the
managed scanner. Native formatter receipts reject an inventory failure, skip a
deleted input and empty inventory, exclude malformed generated output, and
fail for a newly added authored file after setup. Flutter platform exclusion
fixtures accept only generated or vendored Dart and reject tracked and
untracked handwritten files, including test paths.
E2E: N/A — the native subprocess fixtures exercise the runtime and formatter
boundaries directly.

Delivery target: Merge
Delivery: Pending
