# Design It Twice

When the user wants to explore alternative interfaces for a chosen deepening
candidate, generate genuinely different designs before choosing. Based on
"Design It Twice" (Ousterhout): the first idea is unlikely to be the best.

Uses the vocabulary in [deep-modules.md](deep-modules.md) — **module**, **interface**, **seam**, **adapter**, **leverage**.

## Process

### 1. Frame the problem space

Write a user-facing explanation of the problem space for the chosen candidate:

- The constraints any new interface would need to satisfy
- The dependencies it would rely on, and which category they fall into (see [deepening.md](deepening.md))
- A rough illustrative code sketch to ground the constraints — not a proposal, just a way to make the constraints concrete

Show this to the user, then proceed to the alternative designs.

### 2. Generate alternatives

Generate at least three **radically different** interfaces directly. Use
subagents only when the user explicitly requests delegation; then give each
delegated agent one constraint below and verify its output yourself.

Use a separate technical brief for each alternative: file paths, coupling
details, dependency category from [deepening.md](deepening.md), and what sits
behind the seam. Give each alternative a different design constraint:

- Alternative 1: "Minimize the interface — aim for 1–3 entry points max. Maximise leverage per entry point."
- Alternative 2: "Maximise flexibility — support many use cases and extension."
- Alternative 3: "Optimise for the most common caller — make the default case trivial."
- Alternative 4 (if applicable): "Design around ports & adapters for cross-seam dependencies."

Use both [SKILL.md](../SKILL.md) vocabulary and `CONTEXT.md` vocabulary so each
alternative names things consistently with the architecture and domain language.

Each alternative includes:

1. Interface (types, methods, params — plus invariants, ordering, error modes)
2. Usage example showing how callers use it
3. What the implementation hides behind the seam
4. Dependency strategy and adapters (see [deepening.md](deepening.md))
5. Trade-offs — where leverage is high, where it's thin

### 3. Present and compare

Present designs sequentially so the user can absorb each one, then compare them in prose. Contrast by **depth** (leverage at the interface), **locality** (where change concentrates), and **seam placement**.

After comparing, give your own recommendation: which design you think is strongest and why. If elements from different designs would combine well, propose a hybrid. Be opinionated — the user wants a strong read, not a menu.
