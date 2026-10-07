# Reuse main's CI result for the plan baseline

Status: Draft

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

- [ ] Plan-stage check without `--base`, branch point's required checks passed → only changed packages run; a plan-only branch runs no package checks → runner test.
- [ ] Branch point's checks not passed, or no plan stage → every check runs → runner and shipping tests.
- [ ] Skill text and README describe the reuse.
- [ ] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Pending
Evidence: Pending
Execution: One builder in this worktree.

## Risks + recovery

A local tool or environment change since main's CI run is not caught by a plan-only baseline; pre-push and CI still run the affected checks. Recovery is reverting this branch.

## ux_reference

N/A — check behaviour; no visual surface.

## Verification

Result: Pending
Evidence: Pending
Gate: Pending
E2E: N/A — command-line check behaviour proven through the runner in tests.

Delivery target: Merge
Delivery: Pending
