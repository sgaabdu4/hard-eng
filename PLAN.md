# Correct execution-result guidance and missing gate inputs

Status: Complete

## Outcome + scope

Separate Appwrite execution status from response data and repair missing gate inputs without disabling required metrics. Update the canonical Appwrite skill, its linked revision, and the existing gate guidance only.

## Repository context

The Appwrite reference labels async status polling as a terminal result without stating that response bodies are not stored. Official execution documentation explicitly limits response bodies and headers to synchronous calls. Gate guidance forbids weakening checks but does not directly address missing metric inputs.

## Decisions + authorization

Blockers: None

The user authorized reviewing workflow failures, minimal shared fixes and delivery. Follow Writing Great Skills: correct existing routes and semantics, retain valid background execution, and add no runtime wrapper, dependency or prose-matching test. Private audit evidence stays outside public repositories.

## Acceptance + steps

- [x] Canonical execution guidance distinguishes sync response data, async status and durable application results; timeout work routes to that owner.
- [x] Gate guidance requires repairing missing inputs while retaining required metrics and thresholds.
- [x] Existing skill contracts pass and outgoing public content contains only public contracts and generic guidance; final integration follows below.

## Baseline + execution

Result: Passed
Evidence: Starting main 41d706b passed all 17 configured gates, 510 tests, four performance checks and exact main CI 34868224893. Current official Appwrite execution documentation verifies the missing contract; the repository's existing research and test-quality rules remain applicable.

## Risks + recovery

Documentation cannot mechanically certify agent compliance or a service integration. Keep that limit explicit. Preserve synchronous direct response handling, bounded async monitoring and reconciliation. Canonical skill delivery precedes adopting its immutable revision.

## ux_reference

N/A — agent guidance only, with no product UI changes.

## Verification

Result: Passed
Evidence: All 57 existing Appwrite skill contracts pass. One initial route-wording assertion failed and was corrected while preserving the expanded route. Official execution documentation confirms sync bodies/headers and the 30-second bound; reviewed adjacent async background work and durable-result scenarios remain supported. Canonical PR3 merged as 41ca4c9449615702a1059e2aadbd4c74003b6b0d after both exact-head Tests checks passed. The shared change adds no test or runtime machinery. Final integrated gate follows.

Ready for ship — the final Complete gate exited 0 with all configured checks passing. Canonical merged Quality CI 34877867091 also passed. Delivery remains pending below.

Delivery target: Merge
Delivery: Pending — canonical skill PR, Hard Eng PR, exact remote CI and merged revision verification.
