# Reuse main's CI result for the plan baseline

Status: Complete

## Outcome + scope

A plan-stage check run without `--base` compares the branch with the commit it left on the shipping base, when that commit's required CI checks passed. A branch that only adds a plan runs the plan checks and the secret scan; code changes still run their packages' checks and dependents. Without a shipping policy, without GitHub access, or when that commit's checks did not pass, every check runs as before. Fixes issue 241.

Non-goals: changing bare `check` (manual full runs), `--base` behaviour, CI, pre-push or the Stop hook.

## Repository context

Owners:
- `.hooks/shipping.py`: `reused_pull_request` and `_checks` already prove a revision's required checks passed; the new helper sits beside them.
- `.hooks/comments.py` `branch_point`: finds where HEAD left `origin/<base>`.
- `.hooks/hard-eng.py` `check`: picks the comparison base before loading groups.
- `.hooks/gate_config.py` `affected_groups`: a plan-only change already selects only the shared secret scan (`impact --base <merge-base>` printed `docs_only=true`).
- Skill text: `.agents/skills/he/references/gates.md`, `.agents/skills/he-plan/SKILL.md`, `README.md`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked on 2026-10-07 to fix all open issues, review with Codex adversarial review in a loop, and open a PR.

## Acceptance + steps

- [x] Plan-stage check without `--base`, branch point's required checks passed → only changed packages run; a plan-only branch runs no package checks → runner test.
- [x] Branch point's checks not passed, or no plan stage → every check runs → runner and shipping tests.
- [x] Skill text and README describe the reuse.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: main `8f7f8fac` passed its required `hard-eng` CI check run; this branch starts from it unchanged.
Execution: One builder in this worktree.

## Risks + recovery

A local tool or environment change since main's CI run is not caught by a plan-only baseline; pre-push and CI still run the affected checks. Recovery is reverting this branch.

## ux_reference

N/A — check behaviour; no visual surface.

## Verification

Result: Passed
Evidence: `test_plan_stage_check_skips_packages_unchanged_since_a_passed_branch_point` runs a failing package check through `check`: a Draft check with a passed branch point skips it and exits 0; without a passed branch point, or without a plan stage, it runs and fails. `test_branch_point_is_reused_only_after_its_checks_passed` returns the main commit only when its required check run succeeded. A live call from this branch returned main `8f7f8fac` from GitHub. Codex adversarial review (gpt-6-astra) round 1 found no code issues; its only finding was this plan still being Draft.
Gate: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0 (1240 tests, 90.31% line coverage).
E2E: N/A — command-line check behaviour proven through the runner in tests.

Delivery target: Merge
Delivery: Pending
