---
name: he-ship
description: Use for /he:ship final gates: hooks, format, project inventory, no-mistakes, PR evidence, CI, currentness.
---

# he-ship

Stage 4/5. Use `/he:ship` after `he-verify` is clean and work is committed. Finish the gate; do not timebox it.

## Load

- Read `../workflow-help/references/route-map.md`, `../no-mistakes/SKILL.md`, and `references/stage-contract.md` before acting
- Read `../../integrations/no-mistakes/references/axi-workflow.md` and `../../integrations/no-mistakes/references/pr-evidence.md` for Ship-specific worktree and PR-evidence guardrails

## Owns

- Require clean local proof and committed feature-branch work before `no-mistakes axi run`
- Gate through worktree readiness, formatting, project inventory, project quality gates, no-mistakes, PR evidence, review-thread proof, CI, and ship-currentness
- Use `git rev-parse HEAD && git status --short` so `ship-currentness` is after final CI proof with validated head and clean worktree evidence

## Exit

- Code fixes return to `he-implement`; proof gaps return to `he-verify`; gate/evidence fixes stay in `he-ship`
- Open learning/process findings exit with `Next: ready for /he:learn: yes`
- No open learning exits with `Next: loop complete: yes`
