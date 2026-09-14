# Protect public publication boundaries

Status: Complete

## Outcome + scope

Remove private consumer references from current public documentation and change descriptions. Define one publication-privacy owner, routed from shared agent rules, planning and shipping, so private context is excluded before tracked documents are written or external artifacts published.

## Repository context

AGENTS.md routes shared obligations. HE Plan controls tracked planning evidence; HE Ship's references/checks.md owns publication review. DECISION.md and PLAN.md need generic evidence. No runtime helper, denylist, dependency, schema or new file is required.

## Decisions + authorization

Blockers: None

The user prohibits private project information and personal data in public repository artifacts. Existing source repair and delivery authorization covers sanitizing current text and updating guidance. Git history rewriting is outside this change's authorization. One builder owns the change.

## Acceptance + steps

- [x] Current affected PR descriptions and repository documents contain generic technical evidence without private consumer identifiers.
- [x] Shared rules and planning route to the publication boundary before private context is recorded; shipping reviews every public payload.
- [x] Metadata and changed reference links validate; existing source gates pass. No claim of automatic detection of all private context.

## Baseline + execution

Result: Passed
Evidence: Public source revision5c6bb0de5a366b1ff53e6a63ab23b6bb30db08cf passed480 regressions,four performance tests,all17 gates, PR76CI34833412629, mainCI34833608042 and native delivered. The preserved plan was reconciled with this verified main revision before resuming. Runtime implementation remains unchanged.

## Risks + recovery

Editing current text does not remove Git history, edit history, notifications or existing copies. No history rewrite is performed. Private incident details and search terms remain outside this public repository. Secret scanners cannot identify every private business fact; human/agent content review remains required.

## ux_reference

N/A — publication guidance and generic documentation have no visual application surface.

## Verification

Result: Passed
Evidence: Sixteen affected PR descriptions were replaced with generic public-source summaries and read back. Removed private operational evidence and a personal local path from the current decision document without relabeling evidence as synthetic. Both changed skill entrypoints passed the native metadata validator; all three changed routes resolve to the single publication-privacy owner. Diff review confirms guidance and current-text cleanup only, with no runtime changes, new dependency or test file. Ready and Complete checks passed all17 gates; Complete passed480 regressions and four performance tests. Current tracked source and70 current PR titles/bodies have no matches for the known private identifiers checked. These checks establish neither historical erasure nor automatic privacy detection.

Delivery target: Merge
Delivery: Pending — generic PR description, PR CI, exact main CI, native delivered and completed-branch cleanup.
