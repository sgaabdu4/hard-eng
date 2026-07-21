# Flows Stage

## Decide

| Area | Required decision |
|---|---|
| Actors | primary/secondary/admin/support/ops/external/API consumer as applicable |
| Entry | objective + preconditions + permissions + entry point + available information |
| Behavior | actions + decisions + system responses + success + follow-up |
| States | first/returning + empty/populated + loading/slow + stale/large/long content |
| Failure | validation/server/network/dependency/permission/session + partial/duplicate/concurrent behavior |
| Recovery | cancel/undo/delete/abandon/resume/retry + notifications + audit + support visibility |
| Access | keyboard/mobile/responsive/a11y effects when user-facing |

- Each flow = actor → entry → decisions → result/recovery; written behavior = authority; diagram = optional aid.

## Route

1. Derive actor/objective pairs from approved scope + current entry points.
2. Trace each pair → preconditions + permissions + information + main decisions/result.
3. Apply state/failure inventory only where reachable; record `N/A` reason otherwise.
4. Add recovery + notifications + audit + support/follow-up behavior.
5. Reconcile cross-actor handoffs, concurrency, abandonment/resume, and terminology.
6. Assign `F-*` IDs; map each acceptance criterion → ≥1 authoritative written flow; add Mermaid only when it clarifies branching.
7. Async/external/partial/irreversible flow → enumerate boundary timing in `## Failure Model`; broad recovery prose = incomplete.

## Complete

- Every in-scope actor + acceptance criterion maps to ≥1 flow.
- Main, alternate, failure, permission, recovery paths = explicit for every reachable boundary; each non-terminal state has one recovery owner.
- No flow relies on an unstated UI, contract, data, or operational behavior.
- Skip proposal only when change has no user/system flow.
