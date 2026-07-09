---
name: improve-codebase-architecture
description: Scan for deepening opportunities, show an HTML report, then explore the chosen refactor.
user-invocable: true
---

# Improve Codebase Architecture

Surface architectural friction and propose deepening opportunities.

## Contract

- Use `codebase-design` vocabulary for module, interface, depth, seam, adapter, leverage, and locality
- Read `CONTEXT.md` and relevant ADRs before judging seams
- Explore codebase friction before proposing candidates
- Write a visual HTML report to the OS temp directory
- Ask which candidate the user wants to explore
- Use `grill-me`, `domain-modeling`, and `codebase-design` after the user picks a candidate

Load `references/workflow.md` before scanning.
