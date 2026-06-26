---
name: he-verify
description: Use for /he:verify; verification loop with tests, risk review, thermo review, E2E artifacts.
---

# he-verify

Stage 3/5. Use `/he:verify` after implementation or review fixes. Finish proof; do not timebox it.

Read `../workflow-help/references/route-map.md`, `../test-quality/SKILL.md`, and `../e2e/SKILL.md` before acting.

## Contract

- Update `he-state.json` before/after each proof step; record proof findings in `findings[]`; validate it before any ready-yes handoff
- Record every Verify sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before readying Ship
- Targeted tests first; use `test-quality` for assertion, fixture, or gap design
- Run every command in `guardrails[]`; missing or failing guardrails route back to `he-implement`
- Run `node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .` for React/Next, JS/TS, or Flutter work before readying ship
- Add security/perf review when requested or touched; run maintainability review before E2E
- User-visible changes need real UI artifacts
- Auto-fix loop: diagnose failures, return code changes to `he-implement`, update state, rerun affected proof only, repeat until clean or blocked
- Failure loop: no ship handoff until every required Verify sub-stage, proof command, review, artifact, and guardrail is clean or the blocker is explicit
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: ready for /he:ship: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and the next `/he:ship` command. No transcript dump
