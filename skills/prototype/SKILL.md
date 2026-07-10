---
name: prototype
description: Use for throwaway logic or UI prototypes that answer one design question.
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

## Pick a branch

Identify which question is being answered — from the user's prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model feel right?"** -> [LOGIC.md](LOGIC.md)
- **"What should this look like?"** -> [UI.md](UI.md)

The two branches produce very different artifacts — getting this wrong wastes the whole prototype. If the question is genuinely ambiguous and the user isn't reachable, default to whichever branch better matches the surrounding code (a backend module → logic; a page or component → UI) and state the assumption at the top of the prototype.

## Shared Rules

Load `references/shared-rules.md` before creating prototype code.

## When done

The _answer_ is the only thing worth keeping from a prototype. Capture it somewhere durable (commit message, ADR, issue, or a `NOTES.md` next to the prototype) along with the question it was answering. Preserve the prototype as a cleanup candidate until the user approves explicit deletion scope.
