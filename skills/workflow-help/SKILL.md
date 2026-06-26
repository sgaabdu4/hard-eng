---
name: workflow-help
description: Use for workflow, skill, next-step, BMAD comparison, or feature-to-PR routing questions.
---

# Workflow Help

Use as the front door for "what should I do next?" questions.

Load `references/route-map.md` before answering.

Keep the answer focused on:

- stage number
- next `/he:*` handoff
- skills to load
- proof required
- what not to run

Rules:

- `codebase-memory`, `context-mode`, and `terse` are support tools, not stages
- Route by task and risk, not by persona names or BMAD menu codes
- If the request is ambiguous, send it to `grill-me`
- If a feature is ready to build, require a branch or Treehouse worktree before
  implementation.
- If readiness is weak, return `CONCERNS` or `FAIL` and name the missing input
- At stage exit, use the receipt format from `route-map.md`; no transcript dump
- For shipping work, end at `he-ship`/`no-mistakes`, not direct push, unless
  the user explicitly overrides the local gate.
