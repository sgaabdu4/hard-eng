---
name: codebase-design
description: Use for module boundaries, public APIs, ownership, abstractions, wrappers, test seams, or architecture review.
---

# Codebase Design

Use this for structural decisions, not formatting or naming polish.

Load `references/deep-modules.md` before proposing a new abstraction, moving
logic between modules, adding a public interface, or reviewing architecture.

Coordinate with nearby skills:

- For strict diff review, load `thermo-nuclear-code-quality-review` too
- For large feature planning, load `grill-me` or `to-prd` first
- For tests around a chosen interface, load `test-quality` too

Prefer deleting concepts, moving behavior to the canonical owner, and shrinking
public surfaces before adding new layers.
