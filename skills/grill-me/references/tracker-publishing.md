# Tracker Publishing

Use only when the user explicitly asks to publish accepted `plan.md` slices as
tracker cards. `plan.md` remains the canonical plan; cards are execution views.

## Preconditions

- The repo has `docs/agents/issue-tracker.md`; otherwise route to
  `setup-engineering-skills` before any external write
- Every published slice is accepted and has blocking edges, acceptance criteria,
  and verification
- The request authorizes creating tracker records; preview bodies first when the
  requested destination or card grouping is ambiguous

## Card format

Each card contains:

- Title: `<slice id>: <user value>`
- Source plan: relative `plan.md` path and slice id
- User value
- Scope and layers touched
- Dependencies and blocking edges
- Agent-sized tasks
- Acceptance criteria
- Verification commands or checks
- Risks, human gates, and rollback notes when applicable

## Publication

Follow `docs/agents/issue-tracker.md` for the destination and command. Publish one
card per accepted slice unless the user requested another grouping. Preserve
dependency order using the tracker's native blocking links when the contract
supports them, otherwise include a `Blocked by:` field.

After creation, add the returned card identifiers and links to the source
`plan.md` traceability section. A failed partial publication stops further
creates and reports exactly which slices were created and which remain.
