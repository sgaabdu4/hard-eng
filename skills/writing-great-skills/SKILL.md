---
name: writing-great-skills
description: Use for skill writing, skill audits, trigger design, progressive disclosure, pruning, splitting, or optimizing local agent skills.
---

# Writing Great Skills

Start from observed trigger or behavior failures. Define positive triggers,
exclusions, observable outputs, and failure cases before changing the skill.

## Load

- Read `references/skill-writing-method.md` first for the full skill-writing method
- Read `GLOSSARY.md` when using terms such as predictability, invocation, context load, progressive disclosure, leading word, no-op, sediment, or sprawl

## Apply

- Keep active `SKILL.md` files small enough for local hygiene gates
- Move branch-specific or bulky material into `references/*.md`
- Preserve the full upstream idea in references when entrypoint size would weaken deterministic local checks
- Test YAML/metadata validity, trigger precision, non-trigger exclusions,
  reference reachability, context budgets, path safety, and public behavior
- Keep model evaluations release-only, explicitly approved, and bounded; use
  deterministic contracts for guarantees
