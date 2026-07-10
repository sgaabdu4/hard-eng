---
name: he-verify
description: Use for /he:verify; verification loop with tests, risk review, thermo review, E2E artifacts.
---

# he-verify

Stage 3/5. Use `/he:verify` after implementation or review fixes. Finish proof; do not timebox it.

## Load

- Read `../workflow-help/references/route-map.md`, `../test-quality/SKILL.md`, and `references/stage-contract.md` before acting
- Read `../security-review/SKILL.md` or `../performance-rescue/SKILL.md` when requested or touched
- Read `../thermo-nuclear-code-quality-review/SKILL.md` before maintainability review
- Read `../e2e/SKILL.md` only when a user-visible flow changed or real UI proof is required

## Owns

- Run targeted proof first, then every recorded guardrail
- Route failed proof or missing guardrails back to `he-implement`
- Run conditional risk reviews, then thermo review, then E2E last when needed

## Exit

- No ship handoff until tests, reviews, artifacts, and guardrails are clean or explicitly blocked
- Only `PASS` can say `Next: ready for /he:ship: yes`
- Include the compact stage receipt and fresh-session `Handover prompt:`
