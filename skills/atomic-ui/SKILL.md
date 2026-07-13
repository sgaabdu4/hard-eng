---
name: atomic-ui
description: Design or review UI tokens, themes, primitives, components, and visual SSOT.
---

# Atomic UI

## Contract

- Input = accepted UI behavior + current design/style/component owners.
- Visual SSOT = tokens/theme + primitives + composed components + layout/page owners; hierarchy ≠ folder dogma.
- Reusable visual/interaction decision → canonical owner; true one-off constraint may remain local.
- Component earns ownership through behavior, styling, or composition; pass-through component = reject.
- New material product/UX direction → `$he`; this skill preserves accepted design during implementation/review.

## Route

| Need | Action |
|---|---|
| Existing SSOT + local UI edit | Reuse closest token/primitive/component owner |
| Missing/shared SSOT or duplicate visual/component owners | Load [system.md](references/system.md) |
| React/Next implementation | Also `$vercel-react-best-practices` |
| Flutter + Riverpod implementation | Also `$building-flutter-apps` |
| Other Flutter implementation | Existing project design/style owners only |
| Real browser/device proof | `$e2e` |

## Ownership

- `$he-plan` = desired flows/UX/prototype decision.
- `$atomic-ui` = production token/component/layout ownership evidence.
- Stack skill = framework mechanics; `$deterministic-checks` = commands/scanners/gates.

## Complete

- Token/theme/component owner named; reuse/new-owner evidence explicit.
- Loading/empty/error/permission/disabled/focus/hover states covered as applicable.
- Responsive + semantic role/name/state + keyboard/focus + contrast/reflow/motion/touch behavior proven or exact gap reported.
- No duplicated reusable visual value or owner remains in touched blast radius.
