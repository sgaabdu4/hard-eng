# Verify staged updater payloads

Status: Complete

## Outcome + scope

Stage the exact managed update paths in the isolated candidate before verification so VCS-aware checks see newly added files. Migrate only the two known obsolete action pins in existing workflows while preserving project customizations. Managed-asset formatting is a separate change and is excluded from this PR.

## Repository context

.hooks/update.py owns candidate verification and commit staging. .hooks/project_setup.py owns workflow generation. Existing updater and CI tests cover these boundaries. No target edits, hook bypass or new dependency is needed. One small workflow migration helper keeps the existing configuration owner within its complexity budget.

## Decisions + authorization

Blockers: None

The user authorized source repairs, full tests and verified main delivery. Use one isolated builder. Preserve unrelated unfinished source work and consumer checkouts. Public evidence uses synthetic fixtures and generic technical facts only.

## Acceptance + steps

- [x] Newly added managed files, modifications, deletions and links are staged before candidate checks; failures leave the target and its index untouched.
- [x] Exact old checkout and pnpm/setup pins migrate without replacing custom workflow content or unknown versions.
- [x] Focused regressions pass; final Complete gate follows before shipping.

## Baseline + execution

Result: Passed
Evidence: Source c67fced96100e91cea67e1ca773ec5bfc2257524 passed477 regressions,four performance tests,all17 gates, PR73CI34827616947, mainCI34827838302 and native delivered. This checkout begins at that verified revision; a Ready check precedes edits.

## Risks + recovery

Staging is isolated to the candidate index and exact update paths. Existing target hooks remain authoritative. Unknown action versions remain project-owned. This PR does not include managed skill formatting or submodule changes.

## ux_reference

N/A — updater and managed tooling have no changed product UI.

## Verification

Result: Passed
Evidence: Regressions reproduced missing candidate-index paths and stale workflow pins before edits. All36 focused updater/CI tests passed, followed by a supported update transaction proving both pins advance while a customized ten-minute timeout remains unchanged. Candidate tests cover additions, modifications, deletions and links, plus rejection, cleanup and preservation of unrelated staged work. Final Complete gate follows.

Delivery target: Merge
Final Complete gate passed all17 checks,480 regressions and four performance tests. Ready for ship — local implementation and verification complete; delivery not performed.

Delivery: Pending — PR CI, exact main CI, native delivered and supported consumer adoption.
