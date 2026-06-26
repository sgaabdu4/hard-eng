---
name: he-learn
description: Use for /he:learn; durable guard after repeated misses, review loops, or workflow gaps.
---

# he-learn

Stage 5/5. Use `/he:learn` only when `he-state.json` contains open learning findings after repeated misses, review gaps, or ship findings. Finish the durable guard; do not timebox it.

Read `../workflow-help/references/route-map.md`, `../repeated-failure-learning/SKILL.md`, and `../skill-creator/SKILL.md` before acting.

## Contract

- Update `he-state.json` before/after each learning step; validate it before loop-complete yes
- Record every Learn sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before loop-complete
- If learning findings are empty, do not run this stage; `/he:ship` should close with `Next: loop complete: yes`
- Store learning at the narrow owner: source, script, test, hook, route map, or skill
- Use `skill-creator` only for skill/stage-contract changes
- Prefer executable checks; prose-only guidance is last resort
- Failure loop: stay in `he-learn` until every Learn sub-stage is resolved and the durable guard exists and passes
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, and `Next: loop complete: yes/no`. No transcript dump; future runs can resume from state
