# Domain Modeling Workflow

## Scope

This is the active discipline of challenging terms, testing scenarios, and
writing glossary or ADR artifacts when the model changes. Merely reading
`CONTEXT.md` for vocabulary is a normal repo habit, not this skill.

## File Structure

Most repos have a single root `CONTEXT.md` and `docs/adr/`.

If a root `CONTEXT-MAP.md` exists, the repo has multiple contexts. The map
points to each scoped `CONTEXT.md` and any context-specific ADR directory.

Create files lazily. If no `CONTEXT.md` exists, create one only when the first
term is resolved. If no `docs/adr/` exists, create it only when the first ADR is
needed.

## Session Behavior

Challenge glossary conflicts immediately. If the user uses a term differently
from `CONTEXT.md`, cite the mismatch and ask which meaning should win.

Sharpen fuzzy or overloaded words into canonical terms. When "account" could
mean `Customer` or `User`, force the distinction before design proceeds.

Stress-test relationships with concrete scenarios, especially edge cases that
expose boundaries between concepts.

Cross-check claimed behavior against code. If the code and described domain
model disagree, surface the contradiction before writing docs.

When a term is resolved, update `CONTEXT.md` inline using
`CONTEXT-FORMAT.md`. Keep `CONTEXT.md` implementation-free: glossary only, not
spec, scratchpad, or implementation decision store.

## ADRs

Offer an ADR only when all three are true:

- hard to reverse
- surprising without context
- the result of a real trade-off

If any condition is missing, skip the ADR. Use `ADR-FORMAT.md`.
