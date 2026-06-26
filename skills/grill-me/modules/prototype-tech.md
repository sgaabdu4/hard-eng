# Prototype tech stack module

Use before mock-data prototype when mapped `run` or `brief`. During Q&A, update only `plan_draft.md`; write `04-prototype-tech.md` only at stage close, user request, or final synthesis.

## Scope

Decide the frontend/runtime used to build and run the prototype.

Owns:
- Target app stack vs lighter prototype stack
- Runtime/device/browser
- Component-system convention for UI prototypes
- Mock boundary: fixture, mock repo, provider, service
- Mock data shape needed by prototype
- Prototype preview/run command constraints

Out of scope:
- Real backend, auth, storage, realtime, payments, analytics, infra, external APIs
- Full-flow prototype build
- Backend/infra tech stack

## Stage handoff plan

At stage close/final synthesis, `04-prototype-tech.md` includes only relevant decisions:
- Chosen prototype stack/runtime
- Why target stack or lighter stack
- Component-system convention: token-first atomic design, plus stack-specific storage paths/patterns
- Mock boundary decision
- Mock data shape
- Run/preview approach
- Known fidelity gaps only if they affect decisions
- Next-stage handoff for prototype only when useful

Clarity gate:
- Prototype stack chosen or intentionally skipped
- Runtime/device/browser named
- UI prototype component-system convention named, or UI prototype n/a
- Mock boundary named
- Mock data shape named enough to build prototype
- No live backend/API/auth/storage decisions included

## Q pattern

Use `modules/questions.md`. Ask one runtime, mock boundary, component-system, or
preview decision at a time. Keep stack definitions, tradeoffs, evidence, why,
and fidelity gaps for `session_state.md`, stage close, or final synthesis.

## Rules

- If target app stack is known/existing, prototype in that stack/runtime when practical
- If target app stack is unknown or too slow, ask. Default to static HTML/CSS as a styled flow prototype; note migration to target stack later
- For UI prototypes, default component-system convention = token-first atomic design; do not ask the user unless target stack conventions conflict or scope makes it impossible
- Decide mock-data shape + mock service/repo/provider boundaries before prototype build
- Do not decide real backend, auth, storage, realtime, payments, analytics, infra, or external APIs here
- No prototype build before this stage is `accepted` unless user explicitly asks for a quick static styled flow mock
- Do not update `04-prototype-tech.md` per question; record answers in `plan_draft.md` and summarize here only at stage close/final synthesis
