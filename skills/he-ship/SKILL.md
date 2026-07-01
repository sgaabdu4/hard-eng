---
name: he-ship
description: Use for /he:ship; committed final gate with status, hook readiness, no-mistakes axi, PR evidence, CI, currentness.
---

# he-ship

Stage 4/5. Use `/he:ship` after `he-verify` is clean and work is committed. Finish the gate; do not timebox it.

Read `../workflow-help/references/route-map.md` and the upstream
`../no-mistakes/SKILL.md` before acting. Then read
`../../integrations/no-mistakes/references/axi-workflow.md` and
`../../integrations/no-mistakes/references/pr-evidence.md` for Hard Eng's
Ship-specific worktree and PR-evidence guardrails.

## Contract

- Update `he-state.json` before/after each gate step; record gate findings in `findings[]`; validate it before any ready-yes handoff
- Record every Ship sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before loop-complete or Learn readiness
- Require clean local proof and committed feature-branch work before `no-mistakes axi run`
- Run `git status --short`; stop on secrets, `.env*`, unrelated files, or unapproved destructive state
- Run `ensure-worktree-ready.sh --check --require-pre-push .`, `check-project-quality-gates.mjs --require-push-gate .`, `no-mistakes axi run --intent ...`, PR evidence repair with current-head passed evidence after the latest no-mistakes run, `repair-pr-evidence.mjs --check-review-threads` after Copilot or human review, CI follow-through, then `git rev-parse HEAD && git status --short`; record ordered `sequence` evidence so PR evidence is after the latest no-mistakes run, review-thread proof is after PR evidence, CI evidence is after review-thread proof, and `ship-currentness` is after final CI proof with validated head and clean worktree evidence
- Confirm `guardrailInventory.touchedStacks[]` is non-empty and `guardrailInventory.requiredGuardrails[]` covers regex scanners, Git hooks, lint/analyze/typecheck, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention as `required` with matching `guardrails[]` evidence or `not_applicable` with reason/evidence
- Record repeated misses, review gaps, process gaps, or missing future guardrails as learning/process findings for `he-learn`; otherwise skip `learning-capture` with reason/evidence
- Do not trust push dry-runs until project hooks are active and push-blocking guardrails have passed or been explicitly skipped with evidence
- Failure loop: no-mistakes findings stay in `he-ship`; code fixes go to `he-implement`, proof gaps to `he-verify`; no exit until every Ship sub-stage is resolved or explicitly blocked
- If `he-state.json` has open learning/process findings, exit with `Next: ready for /he:learn: yes`; if learning is empty, exit with `Next: loop complete: yes`
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, next handoff, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and `/he:learn` or loop-complete. Only `PASS` can say ready yes or loop-complete yes. No transcript dump
