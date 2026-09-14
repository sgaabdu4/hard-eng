# Migrate the Dart analyzer plugin with its required rules

Status: Complete

## Outcome + scope

Upgrade recognized old Flutter lint plugin pins when installing the modern Dart rule profile, so the command does not leave a contradictory analyzer configuration for the agent to repair.

## Repository context

configure_dart removes old strict-casts/strict-raw-types flags but preserves an installed plugin that still requires them. The canonical Flutter skill template already owns the compatible plugin version. Reuse that template and the existing project setup owner; no dependency resolver or duplicate version registry.

## Decisions + authorization

Blockers: None

The user explicitly requires the command to perform this known migration deterministically. One builder; existing setup.py, project_setup.py, Dart setup tests and README only. No new file, dependency or persistent state. Recognized older numeric/caret pins migrate; absent, newer and custom plugin declarations remain untouched. Use synthetic public fixtures.

## Acceptance + steps

- [x] Known old plugin pins migrate to the canonical template version alongside the modern rules.
- [x] Unrelated plugins, absent/custom/newer declarations and project settings remain preserved.
- [x] Repeated setup is idempotent and the changed transaction still requires actual candidate checks.
- [x] Native analyzer evidence distinguishes the obsolete-plugin contradiction from genuine code diagnostics.

## Baseline + execution

Result: Passed
Evidence: Matching sourced47e367 passed all17 gates,496 regressions,four performance tests, PR80 CI34846438558, main CI34846738375 and native delivered. Reuse this unchanged baseline and validate the Ready declaration before the targeted regression.

## Risks + recovery

Do not replace custom plugin sources or downgrade newer versions. Plugin migration can reveal genuine code diagnostics; those remain required failures. Existing candidate verification and rollback protect the project. Host hook activation remains separate.

## ux_reference

N/A — analyzer configuration has no visual interface.

## Verification

Result: Passed
Evidence: Both recognized old-pin cases failed the original installer assertion; the corrected, focused Dart suite passed16 tests. On Dart3.13.3, a synthetic project using0.10.2 produced CFG_STRICT_ANALYSIS; running the actual installer migrated it to the canonical plugin and removed that diagnostic. CFG_E2E_ENTRYPOINT remained before/after, so this is targeted compatibility proof, not a claim the synthetic app is complete. Final Complete gate passed all17 gates,502 regressions and four performance tests. No checks were weakened and no new repository files/dependencies/state were added. Ready for ship — local verification complete; delivery remains pending.

Delivery target: Merge
Delivery: Pending — PR, exact main CI and native delivered proof required.
