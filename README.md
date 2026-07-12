# hard-eng

![Hard Eng workflow](assets/readme/hard-eng-hero.png)

> **Alpha:** Hard Eng is being rebuilt from scratch. The workflow below is the product direction while each command is rebuilt.

Hard Eng has one entrypoint:

- `$he plan <feature>`
- `$he resume`
- `$he status`
- `$he build`
- `$he ship`
- `$he learn`

`$he → he-plan → he-build (Implement ⇄ Verify) → he-ship → he-learn`

`$he` discovers the active `PLAN.md`, validates its repository state, and routes the next stage. `he-plan` uses `research` to establish current state, then `question-me` for decisions evidence cannot answer. Specialists never own lifecycle state. Context7 is CLI-only and limited to current library documentation.

Use `$he plan <feature>` for a new feature or intentional product-behavior change. Planning moves through repository evidence, feature outcomes, flows, UX, contracts, technical design, testing, rollout, delivery slices, consistency, and final approval. Each stage asks only decisions that evidence cannot settle; it does not advance until you approve the result or explicitly approve a justified skip.

Existing bugs and production incidents stay direct: for example, `fix all Sentry issues` starts with the Sentry workflow, not a new Hard Eng plan. If investigation uncovers a genuinely new product decision, the work escalates to `$he plan` at that point.
