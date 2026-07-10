# Deep Module Design

A module earns its keep when a small interface hides meaningful complexity.
It is shallow when callers still need to understand the internals, ordering,
fallbacks, flags, storage details, or data-shaping rules.

## Vocabulary

Use this vocabulary consistently:

- Module: anything with an interface and an implementation
- Interface: every fact a caller must know, including invariants, ordering, errors, config, and performance
- Implementation: the behavior behind the interface
- Seam: where behavior can vary without editing the caller
- Adapter: a concrete implementation plugged into a seam
- Depth: caller leverage from a small interface hiding meaningful behavior
- Locality: change and verification concentrating in one owner

## Review Questions

- What fact should callers not need to know after this change?
- Can the public surface have fewer methods, parameters, modes, or states?
- If this abstraction disappeared, would complexity vanish or spread to callers?
- Is this boundary real today, or only hypothetical future variation?
- Can tests assert behavior through the same surface callers use?

## Design Rules

1. Move behavior to the owner.
   Put validation, policy, mapping, state transitions, and fallback rules in the
   module that owns the contract.

2. Replace shallow wrappers.
   A one-call wrapper with naming only is not a design improvement.
   Delete it or move real policy into the owner.

3. Prefer one clear contract.
   Avoid stale modes, parallel APIs, optional shapes, silent fallback, and
   caller-specific branches when one explicit model can remove them.

4. Keep dependencies inward.
   Accept dependencies at the boundary instead of creating hidden globals.
   Return data or typed results where practical instead of producing hidden side
   effects.

5. Test through the public surface.
   If a useful test must reach past the interface, the interface is probably the
   wrong shape or the behavior belongs elsewhere.

## Candidate Report

When reporting a design opportunity, include:

- Current owner and public surface
- Caller knowledge that leaks across the boundary
- Proposed owner and contract
- What code, branches, or concepts can disappear
- Tests that prove the behavior through the new surface
- Risks, especially schema, storage, route, or cross-package effects

## Going Deeper

- Use `deepening.md` for dependency categories, seam discipline, and replacing shallow tests
- Use `design-it-twice.md` when comparing multiple interface designs with parallel subagents
