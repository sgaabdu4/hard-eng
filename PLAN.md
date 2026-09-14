# Route repeated bootstrap through the supported updater

Status: Complete

## Outcome + scope

Make the documented bootstrap command install new projects and update recorded installations through the existing transaction. Upstream-managed changes must not be mistaken for local customizations by the initial-install path.

## Repository context

setup.sh always calls setup.py without a previous source. The existing update.update function already selects a verified release, compares managed versions and preserves local changes. Reuse it; do not duplicate migration logic.

## Decisions + authorization

Blockers: None

The user reported this bootstrap failure during the authorized setup repair. One builder; change the existing shell entrypoint, bootstrap test and install output/documentation only. The startup investigation also found host-owned hook trust distinct from project trust; state that prerequisite without auto-approving hooks. No new file, dependency or state.

## Acceptance + steps

- [x] A project without an installed marker still uses initial setup.
- [x] A recorded installation uses the supported update transaction, accepts upstream-managed changes and preserves unrelated local work.
- [x] Existing conflict/rollback/update tests remain passing; shell and source checks pass before delivery.
- [x] Installation guidance identifies Codex hook trust as a separate activation prerequisite; no global trust settings are changed.

## Baseline + execution

Result: Passed
Evidence: Source95c130b and the identical local implementation passed all17 gates,489 regressions,four performance tests, PR78 CI34841193400, main CI34841423043 and native delivered. Reuse this matching baseline; validate the new Ready plan before code edits. The previous local delivery receipt is preserved outside the repository.

## Risks + recovery

Existing updater conflicts remain real blockers. No manual marker changes, file-by-file overwrite or background update concurrent with edits. The bootstrap still requires access to its source; installed updates also need the existing GitHub verification access.

## ux_reference

N/A — shell bootstrap has no visual interface.

## Verification

Result: Passed
Evidence: The actual shell bootstrap passed fresh installation and failed the existing-installation case before repair. Both cases passed after routing recorded installations to the real updater transaction, with release discovery controlled by the fixture and unrelated local work preserved. The final Complete gate passed all17 gates,490 regressions and four performance tests, including existing updater conflict/rollback coverage. Hook trust guidance was checked against official OpenAI documentation; no global trust settings were changed. Actual host activation remains distinct from registration and manual command proof.

Delivery target: Merge
Delivery: Pending — source delivery and observed consumer adoption.
