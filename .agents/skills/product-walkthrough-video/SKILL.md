---
name: product-walkthrough-video
description: Record polished Playwright walkthrough videos of a real web product, then review, approve, and convert them through a hash-bound pipeline. Use when the user asks for a product walkthrough video or e2e video proof of a UI journey.
disable-model-invocation: true
---

# Product Walkthrough Video

Use the bundled recorder + review/conversion scripts; no replacement recorder. Polished recording changes pointer/pacing: raw rendering or timing claims need separate evidence.

Load matching README sections; commands run from this skill's directory.

```mermaid
flowchart LR
  T{Task} -->|Missing runtime dependencies| S[README: Setup]
  T -->|Record / repair / review / deliver| W[README: Workflow]
  T -->|Configure actions / fixtures| C[README: Configuration]
  click S "README.md#setup"
  click W "README.md#workflow"
  click C "README.md#important-configuration"
```

Completion = README's completion gate on the exact delivered MP4. A user-reported defect reopens the journey + enforcement that missed it.
