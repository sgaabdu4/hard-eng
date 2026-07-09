# Improve Codebase Architecture Workflow

## Explore

Read:

- `CONTEXT.md`
- `CONTEXT-MAP.md` when present
- ADRs in the touched area
- relevant source files

Use `codebase-design` language exactly. Avoid drifting into generic "component", "service", or "boundary" wording when the architecture vocabulary gives a sharper term.

Look for friction:

- understanding one concept requires bouncing between many modules
- modules are shallow
- pure functions were extracted only for testability
- tightly coupled modules leak across seams
- code is hard to test through its current interface
- the deletion test says deleting a layer would concentrate complexity

Use subagents through the available multi-agent tool when they can independently inspect different areas. If no subagent tool exists, explore directly.

## HTML Report

Write a self-contained HTML file to the OS temp directory:

```text
<tmpdir>/architecture-review-<timestamp>.html
```

Use Tailwind and Mermaid from CDNs when useful. Each candidate needs:

- files
- problem
- solution
- benefits in terms of locality and leverage
- before/after visual
- recommendation strength: `Strong`, `Worth exploring`, or `Speculative`

End with the top recommendation and ask: "Which of these would you like to explore?"

Do not propose interfaces before the user chooses a candidate.

## Explore Chosen Candidate

Use `grill-me` to walk the design tree:

- constraints
- dependencies
- shape of the deepened module
- what sits behind the seam
- tests that survive

Use `domain-modeling` inline:

- add newly accepted domain terms to `CONTEXT.md`
- sharpen fuzzy terms
- offer an ADR only when a rejected candidate has a durable reason future reviews need

Use `codebase-design` and `design-it-twice.md` when exploring alternative interfaces.
