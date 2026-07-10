# Durable Guard Evidence

Use this when `/he:learn` converts a repeated miss, review gap, workflow gap, or missing future guard into a durable owner.

## Evidence Shape

- Finding: copied from `he-state.json.findings[]` with `ownerStage: he-learn`
- Root owner: the narrowest source, script, test, hook, route map, or skill that should prevent recurrence
- Guard type: deterministic check, model-backed regression, skill/reference update, hook, scanner, or accepted exception
- Proof: command/check result, model-backed regression result, or explicit reason when the guard is prose-only
- Regression: the smallest future signal that would fail if the miss returns
- State update: finding fixed or accepted with artifact paths and proof

## Owner Choice

- Deterministic miss -> validator, scanner, test, hook, or script
- Agent-behavior miss -> skill/reference update plus model-backed route or skill regression coverage
- Skill sprawl or unclear trigger -> use `writing-great-skills` and move branch detail into `references/*.md`
- Process gap across stages -> route-map or stage-contract update, then contract or regression coverage
