---
name: grill-me
description: Interview one clear question before planning/building ideas, features, codebase maps, specs, UI flows, prototypes, or final plans.
---

# Grill Me

## Core contract

- Interview one clear, plain-language Q at a time
- Evidence-only. No evidence = `unknown`
- Persist state in the target repo only when a grill-me session actually starts
- `session_state.md` is the source of truth after compaction/resume; chat memory
  is not.
- User can answer with A/B/C, `use default`, `not sure`, `skip for now`, or a
  custom answer.
- During interview, visible reply = next question only
- Do not batch Qs
- Ask what matters for the chosen depth; mode caps limit scope, not question count
- Ask as many one-by-one Qs as needed until the active stage is aligned; an
  explicitly blocked unknown keeps the parent plan not-ready.

## Start

1. Infer request profile, mode, and candidate active stage from this file first.
2. If mode/stage is clear, do not load `modules/modes.md`; use the matching
   shortcut below.
3. Load `modules/modes.md` only when depth is unclear, the stage map is
   disputed, or a formal Stage Map must be written.
4. Load `modules/session-state.md` after a grill-me session starts, before every
   continuing turn, after compaction/resume, and before final synthesis.
5. Load `modules/orchestration.md` only after a grill-me session starts, when
   resuming a draft, managing files/handoffs, closing a stage, or writing the
   final plan.
6. Load `modules/domain-docs.md` only for existing-code/doc-backed sessions,
   fuzzy domain terms, ADR conflicts/candidates, or doc-update synthesis.
7. Load `modules/questions.md` only before asking an interview question.
8. Load only the active stage module after the stage is selected.
9. Load `modules/stage-handoff.md` only when writing a handoff.
10. Load `modules/final-plan.md` only when synthesizing `plan.md`.

## Mode shortcuts

- `align` / `lite`: decision alignment + plan only. No visual design,
  prototype tech, prototype, or design/code artifact unless requested.
- `understand`: shared understanding only. Explain/map unless user asks to
  plan/build.
- `build-plan`: implementation sequencing + verification. Run vertical
  slices/verification; skip design/prototype unless requested or needed for a risky UX
  unknown.
- `full`: full staged pipeline for broad greenfield/major product work
- `review`: inspect existing plan/spec/docs/code, find gaps/risks, ask focused
  Qs, produce findings or revised plan.
- Domain words like migration, auth, billing, onboarding, redesign, refactor, or
  data cleanup do not create modes. They shape the stage map inside the inferred
  mode.

## Before first Q

- If user says greenfield/new app/empty repo, ask Q1 immediately. Do not inspect
  repo first.
- If existing code/docs/pages matter, inspect them before Q1. Do not ask what
  evidence can answer.
- Q1 resolves the highest-impact unknown that request context cannot answer

## Module index

Core:
- Mode inference and stage-map defaults -> `modules/modes.md`
- Durable session state and resume protocol -> `modules/session-state.md`
- Question format and internal Q record -> `modules/questions.md`
- Drafts, files, stage flow, loop, caps -> `modules/orchestration.md`
- Domain glossary, ADR, and docs-aware grilling -> `modules/domain-docs.md`
- Temp handoff contract -> `modules/stage-handoff.md`
- Final synthesis -> `modules/final-plan.md`

Stages:
- Product plan -> `modules/product.md`
- UI flow -> `modules/ui-flow.md`
- Visual design directions -> `modules/visual-design.md`
- Prototype tech stack -> `modules/prototype-tech.md`
- Mock-data prototype -> `modules/prototype.md`
- Backend/infra tech stack -> `modules/backend-tech.md`
- Vertical slices/verification -> `modules/vertical-slices.md`

## Non-negotiables

- Load the relevant module before working that stage
- Run only stages mapped `run` or `brief`
- Skipped/n/a stages do not create handoff files
- Update `session_state.md` before asking each Q and after recording each answer
- `plan_draft.md` is an answer ledger, not a plan
- Final plan lives in `docs/planning/<slug>/plan.md`; no `99-final-plan.md`
- Final plan absorbs temp docs, then removes them after verification
- Domain docs are lazy: read docs, capture terms/ADRs, write on request/synthesis
- Schema/data/auth/security/deploy/stateful changes need human review,
  rollback/migration notes, and telemetry/audit expectations.
