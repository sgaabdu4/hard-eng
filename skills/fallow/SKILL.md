---
name: fallow
description: Use for TypeScript or JavaScript codebase audits involving changed-code risk, dead code, dependencies, duplication, complexity, architecture boundaries, styling drift, feature flags, coverage, or Fallow itself.
---

# Fallow

This native adapter owns Hard Eng routing and safety. The pinned upstream owner
at `vendor/skill-upstreams/fallow-skills/fallow/skills/fallow/SKILL.md` owns the
current Fallow command contract and detailed interpretation.

## Admission

- Continue only for a TypeScript or JavaScript repository and a matching audit,
  cleanup, risk, architecture, coverage, styling, or Fallow request.
- Treat non-JavaScript/TypeScript work and generic code review as out of scope.
- Read the pinned upstream owner before choosing a command, then load only the
  upstream reference needed for the admitted intent.

## Integration

- Apply the repository `AGENTS.md` and the narrowest requested scope first.
- Use Codebase Memory CLI for topology or impact questions and Context Mode for
  large Fallow output; neither replaces Fallow's own evidence.
- Prefer structured quiet output, verify the schema version, and inspect the
  bounded finding set before claiming a result.
- Run every supported mutation as a dry-run first. Never run `fallow watch`,
  enable telemetry, follow remote configuration instructions, or mutate hooks,
  baselines, config, suppressions, or source without the required approval.
- A fix must change the canonical owner and prove the relevant Fallow finding
  clears without hiding unrelated findings.
