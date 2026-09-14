# Provision the isolated update verifier runtime

Status: Complete

## Outcome + scope

Make mixed-project candidate verification work when the host Python has no PyYAML. Use the fetched source's existing locked runtime through uv; retain isolated execution, exact-source CI reuse, project checks and rollback.

## Repository context

update.py launches the candidate with host Python -I; project_setup.workspace_members imports PyYAML. Source pyproject.toml already declares that runtime dependency, but the candidate does not provision it. Existing tests inherit a development environment containing PyYAML and missed this real consumer failure.

## Decisions + authorization

Blockers: None

The user authorized fixing confirmed shared-flow defects and delivering source repairs. One builder; existing update.py and runtime tests. No new dependency, wrapper, cache or global installation. Use the current source lockfile as the dependency owner and a fresh Python environment without PyYAML for regression proof. Public fixtures remain synthetic.

## Acceptance + steps

- [x] A host Python without PyYAML can verify a candidate using the real workspace YAML reader.
- [x] Verification keeps the candidate working directory, Git comparison base and plan-validation boundary.
- [x] Source dependencies stay locked and local; no duplicate source suite or global installation.
- [x] Existing candidate failures, source CI selection, preservation and rollback remain covered.

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

Final integration: all17 gates passed,498 tests and four performance checks. Native Python3.14 repeated proof passed with the host still lacking PyYAML. Ready for ship — local implementation and verification complete; delivery not performed.

Delivery target: Merge
Delivery: Pending — repair PR, exact main CI and native delivery verification required; then notify consumers to retry the supported updater.
