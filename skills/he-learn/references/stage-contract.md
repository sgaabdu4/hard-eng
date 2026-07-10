# he-learn Stage Contract

- Update `he-state.json` before/after each learning step; validate it before loop-complete yes
- Record every Learn sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before loop-complete
- If learning/process findings are empty, do not run this stage; `/he:ship` should close with `Next: loop complete: yes`
- Store learning at the narrow owner: source, script, test, hook, route map, or skill
- Use `writing-great-skills` for skill/stage-contract changes
- For repeated agent-behavior misses, update or create the relevant skill and add model-backed regression coverage through the route map; for deterministic misses, add the validator, scanner, hook, or test too
- Prefer executable checks; prose-only guidance is last resort
- Failure loop: stay in `he-learn` until every Learn sub-stage is resolved, the durable guard exists and passes, and all learning/process findings are fixed or accepted
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: loop complete: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and loop-complete. Only `PASS` can say loop-complete yes. No transcript dump
