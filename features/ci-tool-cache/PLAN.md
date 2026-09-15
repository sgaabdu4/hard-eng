# Reuse the configured native tool cache

Status: Complete

## Outcome + scope

Use the same native tool directories during workflow bootstrap and gate provisioning. Preserve explicit environment configuration and latest-version resolution. Cache downloaded tool artifacts in the generated workflow using GitHub's native action; do not cache gate results or change assertions, timeouts or package selection.

## Repository context

The workflow sets MISE and pnpm directories below runner.temp, but provision_batch replaces them with Python's unrelated temporary directory. This defeats reuse and makes a cache of the configured directory incomplete. The source workflow has no persistent tool cache. Existing product workflows require their own assertion ownership review and are outside this narrow source fix.

## Decisions + authorization

Blockers: None
The user authorized the performance audit and fixes. Preserve caller-specified native cache paths, use RUNNER_TEMP for defaults on CI, and retain the local temporary-directory default. Reuse the existing runner, native install commands and existing test owners. One small plan records this independently shippable repair; no new runtime file or dependency is needed.

## Acceptance + steps

- [x] Gate provisioning reuses explicit workflow directories and exposes executables from that data directory.
- [x] CI defaults use runner.temp; local defaults remain usable.
- [x] The generated workflow configures native artifact caching while every invocation still resolves latest versions and runs required assertions.
- [x] Focused regression tests and native cold/warm provisioning proof pass.

## Baseline + execution

Result: Passed
Evidence: Upstream main a2e6c8f passed its full source gate and required CI. The performance defect is reproduced by provision_batch unconditionally replacing configured cache paths; existing consumer CI logs independently confirm both temporary roots in one job. No private identifiers are needed for this reproduction.

## Risks + recovery

Artifact caches can be absent or older than an upstream release; native install still resolves latest and downloads missing versions. Existing custom workflows remain preserved and require one-time integration. Cold/cache-hit timing and cache upload cost must be measured before claiming a speedup; this repair alone does not remove duplicate consumer pipelines.

## ux_reference

N/A — CLI provisioning and workflow caching do not change a product UI.

## Verification

Result: Passed
Evidence: The 149 focused provisioning, runner and CI configuration tests pass. A real native scanner install under a CI-style RUNNER_TEMP used that same data directory on both attempts; cold provisioning took 8.43 seconds and warm provisioning 2.72 seconds, with the executable successfully invoked after each. This is a local provisioning measurement, not a claim about whole-pipeline CI savings. Full release gates and hosted cache-hit timing remain part of delivery verification.
E2E: Passed — actual latest-version resolution, installation, executable path verification and scanner invocation completed twice using the configured CI directory.

Delivery target: Merge
Delivery: Pending — PR, main CI and delivered verification remain required.
