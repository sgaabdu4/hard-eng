# Efficient affected checks and scaffold adoption

Status: Draft

## Outcome + scope

Reduce repeated verification and setup cost while preserving required assertions, committed-snapshot pre-push checks, current tools and conservative unknown-impact handling. Support Claude and Codex only, retiring other harness integrations and Context Mode / Codebase Memory MCP during adoption. Release the source before migrating installed consumers. Consumer-specific mappings and deployment changes belong in their own repositories.

## Repository context

Owners: `.hooks/gate_config.py`, `.hooks/dependency_graph.py`, `.hooks/project_setup.py`, `.hooks/hard-eng.py`, `.hooks/ci_setup.py`, `.hooks/tool_setup.py`, language templates and setup/adoption guidance. Existing package selection expands dependents but does not model cross-package file contracts; root JavaScript enumeration includes child packages. CI integration detection accepts a check without a comparison base. Dart templates repeat analysis for boundaries and dead code.

## Decisions + authorization

Blockers: Complete-stage validation and delivery remain pending for the managed-instruction repair and canonical skill pin.
Handoff: Approval
Authority: The user authorized parallel investigation and implementation, model selection, source release followed by upgrades of all installed workspace repositories, removal of confirmed legacy tooling, independent review, PR creation and merge to origin/main. Subsequent instructions prioritize measured runtime and Actions cost, minimal complexity and meaningful tests, and remove all harness integrations except Claude and Codex. The user additionally authorized full Context Mode and Codebase Memory MCP retirement, machine-wide uninstallation and generated-state cleanup, with one combined PR per repository. Later steering retires redundant repository Claude instruction files in favor of shared AGENTS instructions and extends evidence-based legacy cleanup. The user also requires full migration from npm to pnpm where supported, with current official guidance and native edge-case verification. Appwrite Backend is additionally MCP-only for agent operations; its CLI guidance is retired in the same canonical dependency PR. Preserve unrelated work and project-specific assertions. No remote branch-protection changes are authorized.

## Acceptance + steps

- [x] Affected package selection retains transitive and cross-package contract impact, with full checks for uncertain changes → meaningful selection regressions and representative consumer probes.
- [x] Root scans avoid repeating fully owned child-package work without omitting root or unowned sources → source-scope regressions and native command probes.
- [x] Dart boundary/dead-code analysis avoids duplicate work while both failure classes remain enforced → real clean and violating fixtures plus report validation.
- [x] CI setup identifies incomplete integration and generated workflows avoid unnecessary provisioning/cache work → setup regressions, workflow lint and native workflow proof.
- [x] Adoption guidance detects duplicate legacy hook execution and duplicated CI ownership, preserving project-specific checks → installer/registration review and native consumer-shaped migration probes; hosted consumer rollout follows source release.
- [x] Installation and updates retain only Claude and Codex harness integrations, preserving shared instructions and distinct assertions → lifecycle migration checks and source registration inventory.
- [x] Context Mode and Codebase Memory MCP are no longer installed or registered; adoption removes their obsolete launchers and generated state while preserving unrelated integrations → native update and idempotence verification.
- [x] Shared project instructions use AGENTS.md without redundant Claude wrappers; unique scoped/private rules are preserved during migration → installer retirement and pre-write preservation checks.
- [x] The bundled Appwrite skill uses MCP for agent operations; retirement refuses to remove an installed CLI guard still used by project code, and accepts a project-owned replacement → prior-owner preservation and pre-write refusal/removal probes.
- [x] Native tool provisioning and active bundled guidance use pnpm, retaining required install scripts and workspace package-manager ownership → isolated native provisioning, existing contracts and SDK-selection regressions.
- [x] Timings and selection output make actual savings and scope observable without cached pass results → runner checks and measured native execution.
- [x] Independent diff review and full local gates pass → complete-stage check before shipping.
- [x] Generated pnpm bootstrap honors root package-manager declarations on fresh installation and update, preserving package-less repositories and custom action inputs → focused generation/migration regression and native checks. Hosted consumer verification follows the corrective source release.
- [x] Mixed scaffold/application updates reject the scaffold-only shortcut before upstream queries or downloads; plausible scaffold-only changes retain exact source verification → existing mixed-update regression, independent review and native checks.
- [x] Recognize legacy bare and duplicate generated AGENTS imports when retiring CLAUDE wrappers, while preserving custom/private instruction conflicts → existing native installation and conflict cases.
- [x] Accept the exact managed instruction block with only its final separator newline removed, retaining refusal of edited content and duplicate markers → focused native preflight regression and integrated checks.
- [x] Pin the reviewed canonical Flutter skill clarification for HTTP constants and exception-only imports, retaining storage ownership → canonical delivery proof, installed skill validation and integrated checks.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` exited 0 on origin/main 80047129: 1001 tests passed in 110.41 seconds, four performance cases and all native checks passed. The first attempt failed because this new worktree lacked its pinned skill submodules; `git submodule update --init --recursive` restored the required checkout inputs before this passing run.
Execution: Coordinator owns integration and Git. Parallel read-only inventory, consumer audit and official-source research precede independent source implementation slices. Integrated full check and fresh review follow worker checks. Consumer scaffold modifications wait for the verified source release. The canonical skill dependency documentation correction is published first without merging, so the source can pin corrected installed content; its combined adoption PR merges after this source release.

## Risks + recovery

Incorrect dependency mapping can omit checks; unknown inputs must keep full scope. Shared report paths and child-process workers constrain parallelism. Compare command flags and report thresholds before consolidating checks. Preserve latest-tool policy and snapshot isolation. Revert the source change or an individual consumer migration if equivalent enforcement cannot be demonstrated.

## ux_reference

N/A — CLI checks, installer and CI configuration; no product UI changes.

## Verification

Result: Pending
Current repair: A formatter removed the final blank line from an otherwise byte-identical managed instruction file. Adoption correctly retained the file but rejected it as conflicting content before candidate checks. The minimal repair accepts only that exact separator difference. The regression first reproduced one failure with both conflict controls passing; the final code passes all three cases in 0.17 seconds. Thirteen existing installation, idempotence and instruction-preservation cases pass in 16.31 seconds. Independent review, native Ruff format/lint/complexity and diff checks pass; edited instructions and duplicate markers still fail without writes. Canonical Flutter skill PR #14 merged at `432694beefbdd1b3801d471190fe6ef5ece3bc53` after all 12 native checks and a 40.02-second pre-push; both merged-main checks passed in 45 and eight seconds, and the native delivery guard passed. The source now pins that revision, and the installed skill link resolves to the reviewed single-rule clarification. Integrated native Draft verification passed 1060 tests in 79.96 seconds, four performance cases and every configured gate with pytest-xdist's native eight-worker setting. Complete-stage validation and committed-snapshot pre-push remain required. No performance-suite policy change is authorized.
Current migration repair: An installed project with only a managed AGENTS import and a duplicate bare import was rejected before candidate checks. The existing instruction migration now recognizes those two exact legacy forms; custom guidance still requires review. Thirteen existing parametrized installation/conflict cases pass, including both legacy forms, first-install preservation and idempotence. The latest focused run took 51.52 seconds under concurrent external workspace activity; the initial run took 3.57 seconds. Independent review, native complexity/format checks and diff checks pass. Final Ready verification passed 1057 tests in 255.41 seconds, four performance cases and every native gate. The preceding full run reached its unchanged 300-second timeout during concurrent external workspace activity; the retry used pytest-xdist's native four-worker setting with identical scope, coverage and timeout. No timeout or scope was relaxed. The committed-snapshot pre-push check and hosted delivery remain required.
Current follow-up: An installed website migration log show approximately 7.3 seconds spent downloading both source revisions before the scaffold-only shortcut rejects application/workflow changes. A coarse path rejection now avoids that doomed probe without changing the exact proof or full application checks. Five existing focused cases pass in 22.27 seconds, including mixed changes making no upstream query and unverified scaffold-only changes still failing. Independent review, Ruff formatting/lint and diff checks pass. The final Ready check above covers both repairs; no separate hosted benchmark rerun is needed.
Follow-up: Hosted consumer adoption exposed pnpm/setup rejecting generated `version: latest` against a declared root pnpm pin. The correction removes only that redundant input from the standard generated bootstrap when a root pnpm declaration exists. Forty-three focused CI tests pass, including fresh generation, update, idempotence and custom-input preservation. Final Complete verification passed 1055 tests in 54.84 seconds, four performance cases and all native gates after resolving two new type annotations and reusing existing fresh-generation test setup. Independent semantic review found no remaining defect. The corrective source release and hosted consumer verification remain required; earlier release evidence below is retained as history.
Evidence: Final integrated Ready-stage checks passed after the MCP-only skill pin and guarded CLI-file retirement: 1052 tests in 49.07 seconds, four performance cases, configured strict format/lint/complexity/annotations/types, dependency, duplicate/dead-code, workflow, shell, secret, vulnerability and security checks. Native pnpm-only provisioning and package resolution passed; audited consumer pnpm declarations support the required build controls. Independent review found no remaining source defects, including an actual pre-write refusal for an installed guard caller. Both bundled skill revisions are published with successful current-head checks; their existing combined PRs remain pending source release. Complete-stage and committed-snapshot pre-push gates are required before publication.
E2E: Passed — real old-to-new installer migration and repeated setup exited zero with no second-run file changes; unrelated MCP and scoped instruction preservation probes passed. Native Biome and Dart fixtures passed clean/restored and rejected relevant violations. A generated committed-snapshot pre-push completed a real docs-only local Git push in 5.63 seconds. Native Claude AGENTS loading is documented for the installed release, but the isolated model probe exited before returning its marker and remains unverified. Hosted checks remain pending for the published revision.

Delivery target: Merge
Delivery: Pending — PR, current-head CI, guarded merge, verified main CI and published source release before consumer rollout.
