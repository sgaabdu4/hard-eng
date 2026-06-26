---
name: to-prd
description: Use to turn resolved conversation, repo evidence, or a plan into a concise PRD, spec, or implementation brief.
---

# To PRD

Use this only after enough context is resolved to synthesize.
If major decisions are still open, route through `grill-me` first.

Load `references/template.md` before writing the PRD.

Coordinate with nearby skills:

- Use `codebase-design` for module ownership and interface decisions
- Use `test-quality` for behavior-facing testing decisions
- Use `to-issues` after the PRD is accepted and should become work items

Do not publish to GitHub, Linear, or any external tracker unless the user asks
for that publish step explicitly.
