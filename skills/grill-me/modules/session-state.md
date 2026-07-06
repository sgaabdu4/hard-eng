# Session State

Load after a grill-me session starts, before every continuing turn, after
compaction/resume, and before final synthesis.

`docs/planning/<slug>/session_state.md` is the durable control plane.
`plan_draft.md` is only the human answer ledger.

## Template

```md
# <Title> Session State
Updated: <date/session>
Mode: <align | understand | build-plan | full | review>
Profile: <greenfield | brownfield-feature | simple-feature | understanding | codebase-understanding | mixed>
Repo: <greenfield | existing | unknown>
Target artifact: <explanation | decision summary | implementation plan | visual directions | prototype | full plan | unknown>

## Stage Map
- Intake: <run | brief | skip> - <why/evidence>
- Product plan: <run | brief | skip> - <why/evidence>
- UI flow: <run | brief | skip | n/a> - <why/evidence>
- Visual design: <run | brief | skip | n/a> - <why/evidence>
- Prototype tech stack: <run | brief | skip | n/a> - <why/evidence>
- Prototype: <run | brief | skip | n/a> - <why/evidence>
- Backend/infra tech stack: <run | brief | skip> - <why/evidence>
- Vertical slices/verification: <run | brief | skip | n/a> - <why/evidence>

## Position
- Active stage: <stage>
- Stage status: <not-started | interviewing | blocked | accepted | brief | skipped>
- Last question id: <N | none>
- Last answer: <unanswered | recorded | needs-clarification>
- Next action: <ask | record-answer | refine-stage | write-final-plan>

## Last Question
<exact visible question block or none>

## Next Question
<exact visible question block or none>

## Decisions
- <confirmed decision | none>

## Blockers
- <blocker/unknown | none>

## Evidence / Artifacts
- <path:line, user quote, command result, domain doc note, path/url/status, or none>
```

## Rules

- Before every visible Q, persist the exact Q as `Next Question`, move the old
  next Q to `Last Question`, set `Last answer: unanswered`, and set
  `Next action: record-answer`.
- After an answer, update `plan_draft.md`, decisions/blockers, answer status,
  stage status, and next action before asking again.
- On compaction/resume, read `session_state.md` first, then `plan_draft.md`,
  then only the active stage module.
- If state is missing but a draft exists, rebuild minimal state from the draft
  and mark uncertain fields `unknown` before asking.
- If state says `unanswered` and the latest user message is not an answer,
  re-ask `Last Question` exactly.
- Compact but lossless. No hard line cap; keep active questions, blockers,
  decisions, refs, and final-plan evidence.
- Final synthesis removes this temp file after verified `plan.md` absorbs it
  Keep only if content was not copied or ownership is unclear.
