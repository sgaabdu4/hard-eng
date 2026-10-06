# Let the guarded merge bypass a review only the author could give

Status: Complete

## Outcome + scope

When a PR is `blocked` only by a required review that nobody but its author could give, `ship --stage ready` passes and `ship --stage merge` merges with `--admin` after its own head, check and plan guards pass, and reports the bypass. Every other `blocked` cause still refuses. Non-goals: CODEOWNERS parsing, ruleset or classic-protection introspection, bypassing any other requirement.

## Repository context

Owners: `.agents/skills/he-ship/references/checks.md` (merge command guidance), `.hooks/shipping.py` (`_ready_state` requires `mergeable_state == "clean"`; `Shipment`), `.hooks/ship_actions.py` (`run` merge stage calls `gh pr merge --match-head-commit`); tests in `tests/test_shipping.py` and `tests/test_ship_actions.py`. Evidence: issue #233. GitHub reports `blocked` without a reason, so the bypass is proven from PR GraphQL fields (`viewerDidAuthor`, `viewerCanMergeAsAdmin`, `reviewDecision`, head `statusCheckRollup.state`), checked against a real PR, plus the push collaborators list.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix issue #233; that approves the branch commits and PR under `AGENTS.override.md`. Merge follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Blocked PR whose author is the viewer and the only push collaborator (read-only collaborators allowed), with admin merge rights, `REVIEW_REQUIRED`, every head check successful and no conflicts → `verify(..., "ready")` passes and marks the review bypass → `test_ready_bypasses_only_a_review_nobody_but_the_author_can_give`.
- [x] Each of those facts false (another pusher, no admin bypass, not the author, changes requested or no review needed, a failing or pending check, conflicts) → refused with the unmet fact named → same parametrized test plus the existing mergeability cases.
- [x] Merge stage with the bypass → `gh pr merge` gets `--admin` with `--match-head-commit` and the bypass is reported; without it → no `--admin`, no report → extended `test_ship_merge_matches_verified_head_and_checks_result`.
- [x] A clean PR makes no new GitHub calls → `clean` case asserts no GraphQL call; existing shipping tests pass unchanged.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `ebbccc43` + this plan → exit 0, 1203 tests passed.
Execution: One builder.

## Risks + recovery

A repository where others can push but the author is still the sole code owner keeps refusing; the conservative proxy avoids parsing CODEOWNERS. A review submitted between the ready check and the merge call is not re-read; the head-match guard still holds. Recovery: merge manually after review.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_shipping.py` and `tests/test_ship_actions.py` pass (122). Removing any single refusal (author, admin bypass, review decision, head checks, other pushers) or the `--admin` argument fails the new tests. GraphQL field names and shapes checked against a real PR with `gh api graphql`.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0, 1213 tests passed.
E2E: N/A — GitHub merge decisions are proven with recorded API responses; a live bypass needs a protected repository this checkout does not have.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
