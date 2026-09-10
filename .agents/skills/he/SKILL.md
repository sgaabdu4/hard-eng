---
name: he
description: Apply Hard Eng's planning, project context, verification and gate-adaptation guidance when implementing or reviewing code in an installed project.
---

# Hard Eng

Load only matching routes.

```mermaid
flowchart LR
  T{Task} -->|Plan new work / changed scope| P[../he-plan/SKILL.md]
  T -->|Implement / review / deliver| W[references/workflow.md]
  T -->|Adapt / repair checks| G[references/gates.md]
  T -->|Bulk / async / performance| E[references/efficiency.md]
  T -->|Design / change / review tests| Q[references/testing.md]
  click W "references/workflow.md"
  click P "../he-plan/SKILL.md"
  click G "references/gates.md"
  click E "references/efficiency.md"
  click Q "references/testing.md"
```
