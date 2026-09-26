# Count only a branch's own changes against its base

Status: Complete

## Outcome + scope

`check --base <tip>` compares from the merge base with HEAD, so edits made on the base after branching no longer count as the branch's changes for plan applicability, comments or impact. Fixes issue #181. When no merge base exists (unrelated or shallow history), the old diff against the base tip remains. Non-goals: other scope rules.

## Repository context

Owner: `.hooks/gate_config.py` `changed_files`, used by `plans.validate_plans`, `comments.validate_comments` and `changed_packages`. It ran `git diff --name-only <base>`, a diff against the base tip.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix the open hard-eng issues.

## Acceptance + steps

- [x] A branch behind a base that edited a Ready root plan passes with its own Complete plan → `test_base_edits_after_branching_are_not_the_branch_changes`.

## Baseline + execution

Result: Passed
Evidence: Main `846ba75`. The new test failed on that code with the issue's error: "PLAN.md: plan is Ready; this check requires Complete".
Execution: One commit.

## Risks + recovery

CI clones with `fetch-depth: 0`, so the merge base resolves there. Recovery: revert the commit.

## ux_reference

N/A — gate scope with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` → exit 0, 17/17 gates PASS; the plan, comment, package, update, ship and hook suites passed (313 tests).
E2E: Passed — the regression test runs real Git branches: a base that moved on after branching, and a feature branch checked against the base tip.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
