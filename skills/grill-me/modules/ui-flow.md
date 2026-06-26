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
a time. If the user needs to see/compare the flow, inspect existing
routes/components/tokens and create a low-fi project-local route/component/state
artifact first, served on localhost. Use Lavish only to show 2-3 UI-flow options and collect the
decision; save the poll receipt, selected option, rejected options, and chosen
components before closing the stage.
When Lavish is active, the Lavish artifact is the visible question surface:
update it to the current Grill Me question/options before each poll, seed the
conversation with `--agent-reply`, and never ask the next question only in chat
while a stale Lavish artifact is still open.

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
  design SSOT, and keep artifacts in `docs/planning/<slug>/` or the repo's
  planning artifact owner.
- Lavish artifacts must use native form controls or explicit submit controls
  that queue exactly one selected answer; do not rely on annotation clicks for
  dropdowns, radios, or multi-question review state.
- Fix visible layout, state-label, and responsive issues before asking the user
  to review.
- If the user is not aligned, keep asking one question at a time; a parked flow
  decision is a blocker, not readiness.
- Do not update `02-ui-flow.md` per Q; record answers in `plan_draft.md` and summarize only at stage close/final synthesis
- No tech-stack/backend choices here except route/runtime facts from existing code
