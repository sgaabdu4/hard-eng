# Provision the isolated update verifier runtime

Status: Complete

## Outcome + scope

Make fresh setup, update planning, candidate verification and the installed check command work when host Python has no PyYAML. Use the fetched source's existing locked runtime for setup/update through uv; provision the installed CLI's missing YAML package with the existing uv tool. Retain isolated candidate execution, exact-source CI reuse, project checks and rollback.

## Repository context

update.py launches the candidate with host Python -I; project_setup.workspace_members imports PyYAML. Source pyproject.toml already declares that runtime dependency, but the candidate does not provision it. Existing tests inherit a development environment containing PyYAML and missed this real consumer failure.

## Decisions + authorization

Blockers: None

The user authorized fixing confirmed shared-flow defects and delivering source repairs. One builder; existing updater, shell entry point, CLI/tool setup module and runtime tests. No new dependency, wrapper file, custom cache or global installation. Setup/update reuse the source lock; the installed CLI provisions the existing YAML package only when absent. Fresh Python environments expose ambient dependency assumptions. Public fixtures remain synthetic.

## Acceptance + steps

- [x] A host Python without PyYAML can verify a candidate using the real workspace YAML reader.
- [x] Verification keeps the candidate working directory, Git comparison base and plan-validation boundary.
- [x] Source dependencies stay locked and local; no duplicate source suite or global installation.
- [x] Existing candidate failures, source CI selection, preservation and rollback remain covered.
- [x] Fresh installation and update entry points provision the declared source runtime before configuration discovery.
- [x] The installed check CLI handles absent PyYAML without changing host Python and retains real gate failures.

## Baseline + execution

Result: Passed
Evidence: Starting baseline failed: source58fc4a9 passed its existing gate but a real mixed-project update could not import yaml under isolated host Python. A fresh-environment regression reproduced that exact failure against the previous updater. Current repair passed41 runtime/update tests, including preservation and candidate failures, plus the targeted native Python3.14 probe. Full integration follows below.

## Risks + recovery

Keep the candidate as working directory while selecting the source project for dependencies. Source runtime provisioning failure must abort before applying updates; preserve the source lock and target state. Separate lint-rule regressions remain with their existing owner.

## ux_reference

N/A — native hook configuration and text output have no visual interface.

## Verification

Result: Passed
Evidence: uv selects the fetched source project with --locked --no-dev and the host Python version, while executing Python -I in the candidate directory. The native regression uses the real workspace reader, verifies the Git base/plan boundary and unchanged source lock, and confirms the host environment remains without PyYAML. The initial fixture lacked a scaffold directory; after correcting that fixture, the previous implementation failed specifically at import yaml and the repair passed. Runtime/update suites passed41 tests; the targeted Python3.14 run also passed. Ruff and Pyrefly passed. No new dependency, global install or duplicate source suite. Final integrated gate pending.

Expanded runtime proof: native cold-host shell installation failed at the real workspace YAML reader before the bootstrap change, then succeeded while leaving host Python without PyYAML. Existing fresh/update shell regressions passed. The installed CLI regression failed on missing yaml with the previous entry point, then reached the intended shared-gate configuration failure with the repair. Native Python3.14 runtime tests cover both boundaries. Source update planning also uses the locked runtime. The initial candidate-only build passed all17 gates,498 tests and four performance checks; final expanded integration follows.

Delivery target: Merge
Ready for ship — expanded final integration passed all17 gates,499 tests and four performance checks. Both original missing-yaml paths were reproduced; cold setup and installed/candidate CLI fixes have native proof, including Python3.14. No global packages, custom cache or duplicate source suite.
Delivery: Pending — repair PR, exact main CI and native delivery verification required; then notify consumers to retry the supported updater.
