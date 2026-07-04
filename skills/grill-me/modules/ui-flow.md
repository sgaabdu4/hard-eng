# UI flow module

Use for UI flow stage when mapped `run` or `brief`. During Q&A, update only `plan_draft.md`; write `02-ui-flow.md` only at stage close, user request, or final synthesis.

## Scope

Map:
- Screens/routes
- Entry points
- Primary journey
- Empty/loading/error/success states
- Permissions/auth gates
- Back/cancel/retry paths
- Low-fi route/component/state artifact when route/state choices need to be seen

Out of scope:
- Visual layout details
- Prototype implementation
- Backend/infra selection

## Stage handoff plan

At stage close/final synthesis, `02-ui-flow.md` includes only relevant decisions:
- Screen/route inventory
- Entry points
- Primary journey steps
- Required states: empty/loading/error/success/permission
- Navigation rules
- Route/component/state artifact path + status when used
- Next-stage handoff for visual design only when useful

Clarity gate:
- Parent screens/routes named
- Primary journey ordered
- Required states captured
- Permissions/auth gates named or marked n/a
- Any needed visual flow artifact is reviewed, or explicitly skipped

## Q pattern

Use `modules/questions.md`. Ask one route/state/permission/recovery decision at
a time. If the user needs to see/compare, inspect routes/components/tokens and
create a low-fi project-local route/component/state artifact first. Tool split:
Grill Me owns the active question and state files; Impeccable Live reviews the
real app route first. Use a current-design-system mock only when the real
surface cannot exist yet. Capture the answer in a saved `ui-review-receipt`
from the visible review surface: real React route/localhost or Storybook,
Flutter Widget Previewer/Widgetbook/simulator, or local HTML fallback when no
app surface exists. The receipt must be `accepted` and include surface kind,
artifact/receipt paths, saved choices/components paths, the exact Grill Me
question, options shown, review target, selected option, rejected options,
chosen components, tweaks, evidence, and user approval.

## Rules

- Parent routes/screens before child components
- Parent screen choices are UI-flow decisions, not product cleanup, when the
  user asks how it looks, how it flows, or cannot choose from text.
- Name exact route/screen/state
- Include empty/loading/error/permission states before visual design
- UI-flow artifacts are wireflows/maps/state boards, not visual direction or
  prototype. Use existing routes/components/tokens when available; otherwise
  mark them representative.
- For component/state artifacts, load `atomic-ui` and `impeccable`, inspect the
  design SSOT, and use `docs/planning/<slug>/` or repo artifact owner
- Review artifacts must use native form controls or explicit submit controls
  that capture exactly one selected answer; do not rely on annotation clicks for
  dropdowns, radios, or multi-question review state.
- Fix visible layout, state-label, and responsive issues before asking the user
  to review.
- If the user is not aligned, keep asking one question at a time; a parked flow
  decision is a blocker, not readiness.
- If PRODUCT.md or DESIGN.md is missing before a UI artifact/review, route
  through Impeccable setup: `/impeccable init` for PRODUCT.md and
  `/impeccable document` for DESIGN.md. Do not ask for UI approval against
  ownerless context.
- Do not update `02-ui-flow.md` per Q; record answers in `plan_draft.md` and summarize only at stage close/final synthesis
- No tech-stack/backend choices here except route/runtime facts from existing code
