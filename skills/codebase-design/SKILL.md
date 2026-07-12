---
name: codebase-design
description: Use for architecture deepening or review, module boundaries, public APIs, ownership, abstractions, wrappers, and test seams.
---

# Codebase Design

Use this for structural decisions, not formatting or naming polish.

Load `references/deep-modules.md` before proposing a new abstraction, moving
logic between modules, adding a public interface, or reviewing architecture.
Load `references/deepening.md` when assessing a cluster with real dependencies.
Load `references/design-it-twice.md` when the user wants alternative interface
designs or the first obvious interface feels too shallow.

Coordinate with nearby skills:

- For strict diff review, load `thermo-nuclear-code-quality-review` too
- For large feature planning, enter `$hard-eng` Plan first
- For tests around a chosen interface, load `test-quality` too

Prefer deleting concepts, moving behavior to the canonical owner, and shrinking
public surfaces before adding new layers.
