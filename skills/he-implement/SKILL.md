---
name: he-implement
description: Use for /he:implement; owner-first implementation after PASS with TDD, deterministic owner reuse, and guardrails.
---

# he-implement

Stage 2/5. Use `/he:implement` only after `he-plan` is `PASS`. Finish the owner change; do not timebox it.

## Load

- Read `../workflow-help/references/route-map.md`, `../test-quality/SKILL.md`, `references/ssot-owner-reuse.md`, `references/tdd-proof.md`, and `references/stage-contract.md` before acting
- Load touched-area skills only after the owner and stack are known
- For skill or workflow edits, read `../writing-great-skills/SKILL.md`

## Owns

- Reuse or extend the canonical owner before creating anything new
- Prove behavior with red-first or mutation/"make it fail" TDD evidence before owner change
- Add deterministic guardrails for every repeated violation or drift-prone concept

## Exit

- Exit only after required sub-stages, SSOT proof, implementation proof, and guardrail inventory are resolved
- Only `PASS` can say `Next: ready for /he:verify: yes`
- Include `SSOT reused`, `SSOT extended`, `new owners created`, and the fresh-session `Handover prompt:`
