---
name: codebase-design
description: Design or review module boundaries, public APIs, ownership, abstractions, wrappers, or test seams.
---

# Codebase Design

## Contract

- Input = accepted behavior + verified topology + current owners/callers.
- Goal = small public surface hides meaningful policy, state, ordering, errors, and dependencies.
- Prefer delete concept → move behavior to owner → deepen owner → add boundary only for a proven gap.
- One pass-through call, naming-only wrapper, speculative mode, or hypothetical seam ≠ abstraction.
- New product behavior/architecture decision → `$he`; this skill supplies structural evidence only.

## Route

| Need | Load | Complete |
|---|---|---|
| Owner/module/API/wrapper/seam design or review | [workflow.md](references/workflow.md) | Current leak + proposed contract + deletion + blast radius + proof |
| Chosen boundary needs materially different interface options | [alternatives.md](references/alternatives.md) | Compared options + recommendation + user decision/blocker |

## Ownership

- Topology/callers/impact = Codebase Memory CLI + native verification.
- Branch/PR/WIP verdict = `$code-review`; structural result = evidence input.
- Public-behavior test design = `$test-quality`.
- Commands/gates = `$deterministic-checks`.

## Complete

- One canonical owner + explicit public contract + hidden caller knowledge.
- Direct callers + cross-package/data/schema/key/route/test/doc/config effects covered.
- Proposed structure deletes or concentrates complexity; moving/wrapping it = incomplete.
