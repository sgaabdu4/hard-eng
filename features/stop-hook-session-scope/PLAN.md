# Stop hook checks only the session's own change, without test suites

Status: Ready

## Outcome + scope

1. The Stop hook measures changes from the later of the session's starting commit and the branch point on the `shipping.base` remote branch, so work merged by others after the session started is not checked (issue sgaabdu4/hard-eng#306).
2. `check --quick`, which only the Stop hook uses, no longer runs the `tests` role. Format, lint, types, imports, the focused-test ban and the current-files secret scan stay. Pre-push and CI still run every gate.
Non-goals: no opt-in switch; no memory of interrupted checks; no load-based skipping; no new scanners in the quick set.

## Repository context

Owners: [agent_hooks.py](../../.hooks/agent_hooks.py) `completion` (session base) and [reports.py](../../.hooks/reports.py) `QUICK_ROLES`. `plans.default_branch_point` already finds the branch point.
Evidence: a session whose branch was rebased onto a newer default branch kept its old starting commit as the base, so each turn end checked every file merged since. In one consumer project a week-old base gave 2378 files and a quick check with test suites, with no session edits.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix #306 and test it on a consumer project at its default branch. The user chose the scope fix with the Stop check kept on, and then chose to drop test suites from the Stop check (2026-10-15). Codex adversarial review loop before the PR.
Decisions: Use the branch point when it is not already behind the session base: a fast-forwarded or rebased branch then counts only its own commits, and local unpushed work on the default branch keeps the session base. Test suites are the slow part of the quick check; pre-push and CI run them before any change leaves the machine. DECISION.md records the change to the completion rule.

## Acceptance + steps

- [x] Others' merged work after the session started is not checked; a later session edit is → `test_work_merged_by_others_after_the_session_started_is_not_checked`, red before.
- [x] The quick set leaves out `tests` → `test_quick_set_is_chosen_by_role`.
- [x] Consumer project at its default branch: with a week-old session base and no session edits, the old hook started `check --quick` over 2378 changed files; the fixed hook ran no check and returned in 1.1 s. On a real two-file edit (one TypeScript, one Dart), the old quick check passed in 114 s and the new one in 19 s, both at a 1-minute load of 64 to 86.
- [ ] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, consumer run, full check, Codex loop, PR, merge.

## Risks + recovery

An agent can end a turn with a failing test; pre-push and CI still block it before it leaves the machine. Recovery is reverting this branch.

## ux_reference

N/A — hook scope and gate selection only; no product appearance.

## Verification

Result: Pending
Evidence: Pending the consumer run and the full check.
E2E: Pending — the real Stop hook on a consumer project.

Delivery target: Merge
Delivery: Pending — PR CI, then merge.
