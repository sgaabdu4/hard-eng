---
name: writing-great-skills
description: Author or review agent skills and SKILL.md packages; refine triggers, routing, metadata, consolidation and splits.
disable-model-invocation: true
---

# Writing Great Skills

- Scope = user request + settled constraints + existing authorization; skill adds no authority.
- Agent prose = minimum tokens + unambiguous meaning. Use `=`, `→`, `+`, terse bullets/tables where clear; delete filler + repetition. Preserve conditions, actions, exceptions and proof; cryptic abbreviations ≠ useful compression.

## Routes

| Task | Load |
| --- | --- |
| Author/review structure, triggers or boundaries | Core below |
| Create/migrate a package; review metadata, invocation or dependencies | [Package](references/package.md) |
| Repair observed misrouting, missed detail or premature completion | [Repair](references/repair.md) |

## Core

| Check | Required outcome |
| --- | --- |
| Need | Removal loses reusable, non-default behavior; omit generic agent advice. |
| Trigger | Purpose + distinct use; relevant prompts match, unrelated prompts do not. Preserve implicit selection unless user requests explicit-only. |
| Disclosure | `SKILL.md` = routes + essential shared rules. Conditional workflows/examples/detail → references. Each route = load condition + direct link; load only applicable routes. Keep short universal rules inline. |
| Diagram | Branches, sequence or dependencies → Mermaid when clearer/leaner. Terse labels; one representation, no prose duplicate. Simple rule → bullet/table. |
| Split | Same actions + proof → keep together. Split for independent use or observed failure unresolved by clearer completion. |
| Resource | Script = repeated fragile logic; reference = conditional knowledge; asset = copied output. Each needs a current consumer; no mandatory file count. |
| Ownership | Rule + definition + caveat = one owner. Inspect package + relevant siblings/project instructions; consolidate duplicates + remove stale rules. |
| Steering | State target action + observable completion; likely mistake → replacement action. |
| Validation | Available native validator + changed links/tools/skills exist + metadata agrees. Substantial/risky change → representative trigger/non-trigger prompts + actual outcome proof. Run changed scripts; wording tests ≠ behavior proof. |
