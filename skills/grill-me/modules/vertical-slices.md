# Vertical slices/verification module

Use after backend/infra tech stack or when implementation planning is requested, when mapped `run` or `brief`. During Q&A, update only `plan_draft.md`; write `07-vertical-slices.md` only at stage close, user request, or final synthesis.

## Scope

Plan delivery as vertical slices + task waves.

Definitions:
- Vertical slice = narrow end-to-end user value through UI/API/data that can be built, tested, and reviewed independently
- Task wave = set of tasks safe to run in parallel because they do not conflict on files, schemas, data, routes, or decisions
- Blocking edge = another slice/task that must finish before this one can start
- Frontier = unblocked slices/tasks that can start now
- Acceptance criteria = observable pass/fail conditions for user value
- Verification = tests, commands, manual checks, rubric, or prototype review proving criteria

Owns:
- Slice inventory
- Dependencies + execution order
- Blocking edges + current frontier
- Small reviewable tasks
- Acceptance criteria per slice
- Verification per slice
- Parallel-safe waves
- High-risk controls

Out of scope:
- Re-opening product/UI/backend choices unless blockers conflict
- Implementing code
- Changing schemas/routes/storage keys; record blast-radius requirement only

## Stage handoff plan

At stage close/final synthesis, `07-vertical-slices.md` includes only relevant decisions:
- Source requirements/decisions consumed
- Slice table or bullet list, whichever is clearer
- Task waves
- Blocking edges and current frontier
- Acceptance criteria
- Verification plan
- High-risk controls only when risk exists
- Final plan inputs

Slice table when useful:

```md
| Slice ID | User value | Layers touched | Dependencies | Tasks | Acceptance criteria | Verification | Risks | Gate |
|---|---|---|---|---|---|---|---|---|
| S1 | <value> | <UI/API/data/tests> | <deps> | <small tasks> | <pass/fail> | <cmd/manual/check> | <risk/owner> | <ready/blocked> |
```

Clarity gate:
- Every required capability maps to at least one slice
- Each slice has user value, layers touched, dependencies, tasks, acceptance criteria, verification, risks
- First slice is a walking skeleton when useful: minimal end-to-end path proving architecture
- Blocking edges are explicit; the plan names the current unblocked frontier
- Parallel waves avoid file/schema/data/API conflicts
- High-risk changes name human review, rollback/migration notes, and telemetry/audit expectations

## Q pattern

Use `modules/questions.md`. Ask one slice, dependency, wave, acceptance, or
verification decision at a time. Keep slice/task definitions, tradeoffs,
evidence, why, and review/failure scenarios for `session_state.md`, stage close,
or final synthesis.

## Rules

- Prefer thin end-to-end slices over horizontal layers
- Prefer tracer-bullet slices that leave the system demoable or verifiable after
  each slice
- Put the smallest useful walking skeleton first unless code/evidence proves another order
- Make tasks small enough for one focused agent/review
- Do not parallelize tasks touching the same schema, route, storage key, generated file, shared type, or migration
- Do not create separate ticket artifacts unless the user explicitly asks to
  publish tracker cards; `plan.md` owns slices by default
- On an explicit tracker-card request, load
  `../references/tracker-publishing.md`; it owns card format and publication
- Acceptance criteria should include happy path plus relevant fail/edge/permission/offline/perf/security cases
- Verification should include exact command/check where known; otherwise mark `unknown` and block only if high risk
- Schema/data/auth/security/deploy/stateful slices require human review gate, rollback/migration notes, and telemetry/audit expectations
- Do not update `07-vertical-slices.md` per question; record answers in `plan_draft.md` and summarize here only at stage close/final synthesis
