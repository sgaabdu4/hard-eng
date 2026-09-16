# Current-files scanning and brownfield migration

Status: Complete

## Outcome + scope

Scan every authored current source file for the configured Gitleaks files gate while omitting ignored generated output. Preserve tracked submodules and in-repository skill aliases, reject unsafe paths, and retain native SARIF paths. This plan does not alter history scanning, scanner thresholds, or application repositories.

Brownfield follow-up: prevent incompatible retained scanner commands from being installed; add configured PR checks alongside maintenance-only workflows; guide agents to finish routine migrations and verify final committed content. Preserve existing quality-workflow owners and unrelated customizations. No generic migration framework or automatic rewriting of arbitrary project commands.

## Repository context

`.hooks/hard-eng.py` owns native gate execution and `.hooks/gate_config.py` owns role validation. The source tree uses Gitlinks and tracked aliases to canonical skill sources, so a direct directory scan includes ignored generated output while a file snapshot needs cycle-safe recursive copying.

## Decisions + authorization

Blockers: None

The user authorized the isolated canonical repair. The snapshot wraps only the existing `secrets-files` native `gitleaks dir .` command. Inventory, copy, and path-validation failures block the gate; no secret values appear in public artifacts.

The user subsequently authorized fixing the confirmed migration gaps and updating origin/main, with YAGNI, speed and efficiency. One coordinator owns integration and shipping; Terra workers own the disjoint CI adaptation and existing migration-guidance files.

## Acceptance + steps

- [x] Initialize consumer submodules in candidate verification; prove tracked aliases resolve and temporary worktrees are removed on success and failure without changing the primary checkout.
- [x] Reject uninitialized scanner submodules rather than silently omitting their contents; retain recursive CI checkout.
- [x] Reject scaffold-only updates whose retained files-scanner commands conflict with the candidate validator, before changing the installed revision or local files.
- [x] Prove an existing wrapped files scanner is rejected, a native scanner updates successfully without running application checks, and local work is preserved.
- [x] Generate configured canonical PR checks beside maintenance-only workflows, preserving actual or uncertain existing quality owners.
- [x] Prove missing ignored skill targets fail in a clean committed checkout and tracked targets restore success.
- [x] Update existing guidance to finish routine migration, retire user-designated obsolete tooling before repairing gates, preserve custom behavior, and verify actual committed and hosted results before completion.
- [x] Snapshot tracked and nonignored authored files, omitting only Git-declared working-tree deletions.
- [x] Recursively include Gitlinks and safe in-repository aliases while rejecting external links and directory-link cycles.
- [x] Preserve SARIF source paths and reject report paths escaping through absolute paths or symlinks.
- [x] Prove the native role command, scanner failure propagation, submodule coverage, and negative path controls in focused tests.
- [x] Run the configured source native gate with this plan as the applicable authorization record.

## Baseline + execution

Result: Passed
Evidence: Untouched `c5b6466` passed the relevant runner subset (134 tests). The repair branch then passed Ruff, Pyrefly, and 144 focused scanner/runner tests.
Follow-up baseline: `python3 .hooks/hard-eng.py check --plan-stage Draft` passed on 2026-09-16 before implementation. One builder will add the existing native-command compatibility check to the isolated updater candidate; a Terra reviewer independently confirmed the cause. Preserve project configuration rather than automatically rewriting wrappers.
Expanded migration baseline: the committed updater repair passed all 712 tests and 17 source gates, including Complete, before CI/guidance work. Reuse that matching implementation proof; run plan readiness with `--base HEAD` and then focused regressions plus one integrated Complete gate.

## Risks + recovery

Snapshots can miss files only if Git inventory is inaccurate or a path cannot be copied; those cases fail the gate. A recursive link can loop only when its resolved directory is an active ancestor; the copier rejects that condition before recursion. Revert the task-owned helper and wiring if a supported native scan regresses.

## ux_reference

N/A — native source-security gate behavior has no product interface.

## Verification

Result: Passed

Evidence: The integrated Complete gate passed all 719 tests (134.27 seconds), 88.63% line coverage, and all 17 configured checks. Independent Terra reviews found no remaining blocker after the corrections below. No new files, dependencies or migration framework were added.

- Retained scanner wrappers reproduce the incompatible-command failure before installation. Native scanner commands update successfully without running application gates for scaffold-only changes. Validation imports trusted source modules; a committed shadow-module regression proves candidate hooks cannot replace them.
- Maintenance-only workflows receive the configured canonical PR check; existing quality owners, malformed workflows and custom required-check names are preserved. All 22 CI tests pass. Generated CI already fetches recursive submodules.
- A real submodule and tracked alias reproduced the updater failure before the fix. Native recursive initialization now reads pinned content in candidate verification; both success and gate-failure cases remove the temporary worktree and preserve primary local edits and initialized configuration.
- The scanner retains submodule and alias coverage and rejects uninitialized Gitlinks with an actionable error. A real clone proves ignored required skill targets fail until committed. All 14 scanner/update integration cases pass.
- Existing guidance requires routine migration completion, retirement of user-designated obsolete tooling before gate repair, and committed/hosted verification when shipping is authorized.

Expanded baseline: 716 tests passed, but duplicate-code detection found repeated CI test setup. The preservation cases now share their existing parameterized test; the exact duplicate gate passes. New updater regression coverage lives next to scanner tests to keep the existing test files below the file-size limit.

E2E: Passed — temporary Git repositories exercise native scanning, updates, pinned submodule aliases, failed-gate cleanup, missing committed skill targets, and preservation of local work. No consumer application repository was changed.

Delivery target: Merge
Delivery: Pending — isolated pre-push, required PR/main CI, and public updater verification on a synthetic submodule consumer remain required.
