# Backend/infra tech module

Use after prototype approval when mapped `run` or `brief`. During Q&A, update only `plan_draft.md`; write `06-backend-tech.md` only at stage close, user request, or final synthesis.

## Scope

Plan:
- Architecture boundaries
- Data model/schema
- APIs/events/realtime
- Auth/permissions
- Storage/files
- Integrations
- Infra/deploy/env
- Tests/observability/migrations
- High-risk controls: human review, rollback/migration notes, telemetry/audit expectations

Out of scope:
- Product positioning
- Visual layout
- Prototype frontend/runtime; use `04-prototype-tech.md`
- Mock prototype changes except implications

## Stage handoff plan

At stage close/final synthesis, `06-backend-tech.md` includes only relevant decisions:
- Architecture summary
- Data model/schema notes
- API/event/realtime plan
- Auth/permission plan
- Storage/integration plan
- Infra/env/deploy notes
- Test/observability/migration plan when needed
- High-risk controls only when risk exists
- Next-stage handoff for vertical slices/verification only when useful

Clarity gate:
- Prototype approval confirmed or prototype n/a with evidence
- Backend boundaries named
- Data ownership/schema risks captured
- Auth/permission model named or marked n/a
- Test strategy named
- Schema/data/auth/security/deploy/stateful risks have human review gate, rollback/migration notes, and telemetry/audit expectations

## Q pattern

Use `modules/questions.md`. Ask one backend capability decision at a time:
data/API/auth/storage/deploy/test boundary. Keep definitions, tradeoffs,
evidence, why, and failure/scale/security scenarios for `session_state.md`,
stage close, or final synthesis.

## Rules

- Do not plan backend/infra before prototype approval when prototype runs
- Use existing stack if code proves it unless user says migration
- Separate product decision from impl choice
- Do not update `06-backend-tech.md` per question; record answers in `plan_draft.md` and summarize here only at stage close/final synthesis
- For schemas/indexes/storage keys/routes, run blast-radius search before changing code
- For Appwrite/Auth/TablesDB/Storage/Functions/Realtime, invoke `appwrite-backend`
