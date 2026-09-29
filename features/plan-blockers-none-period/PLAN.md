# Accept a bare "None." as no Blockers at every plan stage

Status: Complete

## Outcome + scope

`Blockers: None.`, `None;` and `None:` count as no blockers, so a Ready or Complete plan that writes them passes the Blockers check, and a Draft reads them the same way. Every form already accepted is still accepted: `None`, `None. note`, `None — note`. `None` followed by other words with no separator (`None blah`, `None yet`) is still a blocker. Non-goals: other plan fields and the Draft handoff rules.

## Repository context

Owner: `.hooks/plans.py` `no_blockers`, used by `draft_handoff` (Draft), `planning_feedback` (Stop notice) and `validate_plan` (Ready/Complete). Before this change, its pattern required whitespace after `.`, `;` or `:`. A bare `None.` failed Ready/Complete with "unresolved Blockers", and Draft took the same text as a concrete decision. Two installed projects reported the rejection.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The user authorized one Hard Eng PR, squash merge, verified main CI, a GitHub release following the previous pattern and remote branch deletion. Consumers are described generically.

Widen the single pattern at its owner, `None(?:[.;:](?:\s.*)?|\s+[—–-]\s.*)?`, so all three stages share one decision. This plan's own `Blockers: None.` is validated by the real gate.

## Acceptance + steps

- [x] `None`, `None.`, `None;`, `None:`, `None. note`, `None — note` → Complete passes; `None of…`, `None yet`, `None blah` and a real blocker → "unresolved Blockers". Covered by the extended `test_blockers_none_may_carry_a_note` in `tests/test_plans.py`.
- [x] Draft and Complete agree on `None.`: a Draft Clarification with `Blockers: None.` is rejected for lacking concrete Blockers, and the same text passes Complete. Covered by `test_draft_and_complete_agree_that_none_period_has_no_blockers` in `tests/test_planning_handoffs.py`.
- [x] Full gate passes, including this plan's `Blockers: None.` → `python3 .hooks/hard-eng.py check --base origin/main`.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `de10c04d` → exit 0, 1090 tests in 133 s, 197 s total. An earlier run with 4 workers at load average ~60 hit the 300 s tests timeout.
Execution: One builder. Tests first (red), then the one-line fix, then the integrated gate.

## Risks + recovery

The only newly accepted inputs are `None` directly followed by one `.`, `;` or `:` at the end. Recovery: revert the commit.

## ux_reference

N/A — plan validator pattern with no product UI.

## Verification

Result: Passed
Evidence: Red on unchanged `plans.py`: the `None.`, `None;` and `None:` params fail, and the agreement test fails with "DID NOT RAISE" because Draft took `None.` as a concrete blocker. Green after the fix: 97 passed in the two plan test files. Full `python3 .hooks/hard-eng.py check --base origin/main` → exit 0, 1097 tests in 216 s, 90.61% line coverage, 262 s total.
E2E: Passed — the real `hard-eng.py check --base origin/main` validates this Complete plan, whose `Blockers: None.` failed as unresolved before the fix.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green on the merged SHA, GitHub release.
