# Current-files Gitleaks scope

Status: Complete

## Outcome + scope

Scan every authored current source file for the configured Gitleaks files gate while omitting ignored generated output. Preserve tracked submodules and in-repository skill aliases, reject unsafe paths, and retain native SARIF paths. This plan does not alter history scanning, scanner thresholds, or application repositories.

## Repository context

`.hooks/hard-eng.py` owns native gate execution and `.hooks/gate_config.py` owns role validation. The source tree uses Gitlinks and tracked aliases to canonical skill sources, so a direct directory scan includes ignored generated output while a file snapshot needs cycle-safe recursive copying.

## Decisions + authorization

Blockers: None

The user authorized the isolated canonical repair. The snapshot wraps only the existing `secrets-files` native `gitleaks dir .` command. Inventory, copy, and path-validation failures block the gate; no secret values appear in public artifacts.

## Acceptance + steps

- [x] Reject scaffold-only updates whose retained files-scanner commands conflict with the candidate validator, before changing the installed revision or local files.
- [x] Prove an existing wrapped files scanner is rejected, a native scanner updates successfully without running application checks, and local work is preserved.
- [x] Snapshot tracked and nonignored authored files, omitting only Git-declared working-tree deletions.
- [x] Recursively include Gitlinks and safe in-repository aliases while rejecting external links and directory-link cycles.
- [x] Preserve SARIF source paths and reject report paths escaping through absolute paths or symlinks.
- [x] Prove the native role command, scanner failure propagation, submodule coverage, and negative path controls in focused tests.
- [x] Run the configured source native gate with this plan as the applicable authorization record.

## Baseline + execution

Result: Passed
Evidence: Untouched `c5b6466` passed the relevant runner subset (134 tests). The repair branch then passed Ruff, Pyrefly, and 144 focused scanner/runner tests.
Follow-up baseline: `python3 .hooks/hard-eng.py check --plan-stage Draft` passed on 2026-09-16 before implementation. One builder will add the existing native-command compatibility check to the isolated updater candidate; a Terra reviewer independently confirmed the cause. Preserve project configuration rather than automatically rewriting wrappers.

## Risks + recovery

Snapshots can miss files only if Git inventory is inaccurate or a path cannot be copied; those cases fail the gate. A recursive link can loop only when its resolved directory is an active ancestor; the copier rejects that condition before recursion. Revert the task-owned helper and wiring if a supported native scan regresses.

## ux_reference

N/A — native source-security gate behavior has no product interface.

## Verification

Result: Passed
Follow-up (2026-09-16): a retained project-specific files-scanner wrapper reproduced the native-command validation failure. The new updater regression failed before the fix because the update incorrectly succeeded, while its native-command case passed. Candidate verification now invokes the existing files-scanner validator before accepting a scaffold-only update. The 48 focused tests and 712 full-suite tests passed; the first Complete run failed dead-code analysis because a helper was referenced only inside a subprocess string. Removing that unnecessary helper and keeping the check in the existing candidate subprocess restored the dead-code pass; both updater regression cases passed again. Custom commands are not rewritten; other repositories were not changed. Delivery of this follow-up remains pending.
Evidence: The normal Ready-stage native gate passed all configured checks: 697 tests in 109.57 seconds, managed Gitleaks 8.30.1 scanned the initialized canonical source tree with no findings, and a generic positive fixture retained its relative SARIF source URI without exposing the marker value.
E2E: Passed — temporary Git fixtures invoke the native files-gate owner with tracked, untracked, ignored, deleted, submodule, alias, and symlink-cycle inputs. The follow-up also exercises real Git update transactions: incompatible scanner config fails with HEAD, marker, config and worktree unchanged; a native command updates successfully without running the fixture's failing application gate.

Delivery target: Merge
