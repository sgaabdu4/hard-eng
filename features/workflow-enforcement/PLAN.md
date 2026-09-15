# Enforce runtime proof and make affected checks actionable

Status: Complete

## Outcome + scope

Make omitted end-to-end proof fail at stage boundaries, retain task authority after Stop feedback, and make conservative full-suite selection understandable and actionable during setup. Preserve native gates, existing customizations and delivery requirements. No new workflow engine or global host settings.

## Repository context

The existing plan validator permits Complete without a distinct runtime disposition; nonvisual changes can still affect user journeys. Gate selection already supports transitive dependencies but setup leaves mappings unknown. Session Stop rejects missing checks but its repair imperative can override a read-only actor's task. These existing owners can carry the repair.

## Decisions + authorization

Blockers: None

Autonomous source repair, meaningful native acceptance, whole-repository Astra then Fable review, and PR/main delivery are authorized. Consumer trials use isolated fixtures first; product pilot access and data boundaries remain separate. One builder owns plan/Stop contracts; an independent Terra builder owns affected selection/setup, followed by integrated verification.

## Acceptance + steps

- [x] Ready requires a concrete E2E disposition; Complete rejects pending local proof. Post-deploy proof requires Deploy and configured delivery verification.
- [x] Stop feedback preserves task scope and permits honest blockers without unauthorized repair. Native read-only and authorized runs demonstrate the boundary.
- [x] Affected selection preserves transitive/shared impact; unknown dependencies remain conservative with actionable setup diagnostics.
- [x] Native greenfield/brownfield installer and stage probes preserve customization and expose unfinished adaptation accurately.
- [x] Service setup selects the actual endpoint/authentication branch, reuses known choices, reports unresolved optional setup while installing the core, rejects conflicting configuration before writes, and distinguishes configuration from live readiness.
- [x] Skill distribution excludes local dependencies/caches; scanner provisioning, native import configuration and explicit Dart settings preserve their actual execution contracts.
- [x] CI adaptation preserves existing jobs for deliberate assertion ownership and requires measured project budgets. Independent native uv commands are not serialized behind a redundant cache lock.
- [x] Whole-repository adversarial findings are repaired and affected verification passes; the native completion gate remains required before the ready-for-ship handoff.

## Baseline + execution

Result: Passed
Evidence: `uv run --no-project --with pyyaml python .hooks/hard-eng.py check --plan-stage Draft` exited 0 on the starting implementation c15c6c65a9f74b87de9d0a5b360f539dd29e63e9. The first attempt failed because this isolated worktree lacked its pinned skill submodules; initializing those dependencies corrected the environment without source changes.

First slice: negative and positive native plan checks for missing, pending and delivered runtime proof. Dependency diagnostics can proceed independently after the baseline and Ready gates.

## Risks + recovery

New required plan declarations must fail clearly for active old plans rather than silently certifying them. Dependency inference must not invent cross-service edges or skip unknown consumers. Keep scope in existing owners and use temporary Git fixtures; preserve external state.

## ux_reference

N/A — this changes CLI workflow validation and guidance without a visual interface.

## Verification

Result: Passed
Evidence: The final native Complete gate passed 618 tests, four performance cases and every configured static/security check, including zero duplication. The execution matrix passed 129 tests, and extended Fallow wrapper validation passed 13 cases. A native uv overlap regression failed with the redundant lock and passed after removal, including failure propagation. Native Import Linter kept split contracts; the official Dart MCP initialized and listed tools; all three recorder browser smoke tests passed. Whole-repository Astra high and Fable 5.1 reviews were completed in order, including a Fable follow-up over previously omitted runtime owners. Concrete findings were repaired; the proposed Marionette syntax change was withdrawn after native SDK confirmation.
E2E: Passed — native shell bootstrap/update and CLI stage fixtures proved installation, customization preservation, negative proof rejection and corrected acceptance. Native Luna/max greenfield/brownfield startup probes reported unfinished adaptation without unauthorized edits. These source-contract probes do not establish published curl acceptance, external host authentication or a product pilot; those remain separate delivery work.

Delivery target: Merge
Delivery: Pending — native PR/main CI and delivered verification follow local acceptance. A separate product pilot remains outside this source delivery claim.
