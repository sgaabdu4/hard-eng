---
name: he-learn
description: Use for /he:learn; durable guard after repeated misses, review loops, or workflow gaps.
---

# he-learn

Stage 5/5. Use `/he:learn` only when `he-state.json` contains open learning/process findings after repeated misses, review gaps, workflow gaps, missing future guards, or ship findings. Finish the durable guard; do not timebox it.

## Load

- Read `../workflow-help/references/route-map.md`, `../repeated-failure-learning/SKILL.md`, `../writing-great-skills/SKILL.md`, `references/durable-guard.md`, and `references/stage-contract.md` before acting
- For skill edits, read `../writing-great-skills/SKILL.md` and keep details in references

## Owns

- Store learning at the narrow owner: source, script, test, hook, route map, or skill
- Prefer executable checks; prose-only guidance is last resort
- Add model-backed regression coverage for repeated agent-behavior misses

## Exit

- Stay in `he-learn` until the durable guard exists, passes, and findings are fixed or accepted
- Only `PASS` can say `Next: loop complete: yes`
- Include the compact stage receipt and fresh-session `Handover prompt:`
