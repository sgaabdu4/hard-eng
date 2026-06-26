# Final plan module

Use when the interview is done or the user asks for an artifact. Infer the
smallest useful artifact; ask one clarification only if output shape is unclear.

## Inputs

Read `session_state.md`, `plan_draft.md`, stage handoffs/artifacts, relevant
`PRODUCT.md`, `DESIGN.md`, token/design-system owner paths, `CONTEXT.md`,
`CONTEXT-MAP.md`, ADRs, or domain notes.

Do not expect a Stage Map in `plan_draft.md`; the draft is an answer ledger.
Do not create/read handoff files for skipped or n/a stages.

Include only goal-relevant decisions, Q&A, paths, checks, proof, traceability,
controls, risks, domain/ADR changes, and explicitly blocked unknowns.

## Synthesis flow

1. Read session state + draft answer ledger + existing stage handoffs/artifacts
   if present.
2. Infer artifact depth from the request and gathered answers.
3. If output shape is still unclear, ask one Q: decision summary, implementation plan, visual design/prototype, or full spec.
4. Check active stages are aligned or explicitly blocked. Docs may accept product/domain
   decisions only; UI/visual need documented screen-flow/look approval.
5. Detect conflicts between draft, handoffs, artifacts, and user answers.
6. If conflict/blocker exists, ask one Q; do not finalize.
7. Ensure product changes update `PRODUCT.md`; design/UI/token changes update
   `DESIGN.md` and the token owner. If missing, block or create/update them.
8. Write `docs/planning/<slug>/plan.md` as the canonical artifact, sized to need.
9. If requested or needed, update confirmed `CONTEXT.md` glossary terms or ADRs
   using `modules/domain-docs.md`.
10. Re-read `plan.md`; verify needed decisions, context docs, artifacts, checks, proof, risks, unknowns, and traceability.
11. Remove absorbed temp state after verification: `session_state.md`,
    `plan_draft.md`, temp handoffs, empty `stages/`.
12. Preserve artifacts: designs, prototypes, mock data, fixtures, screenshots,
    diagrams, code, and user-created docs.
13. End with artifact, cleanup, choices. Build-plan: implement, review/edit, or
    stop. Sliced plan -> readiness + Treehouse/worktree/branch + first slice.
    `to-issues` only for missing/tracker cards.

## Final plan requirements

`plan.md` includes only what the artifact needs: summary, assumptions,
decisions, Q&A, artifacts, domain/ADR notes, checks, proof, traceability,
controls, risks, blocked unknowns, and owner/next.

Do not write `99-final-plan.md`; final synthesis lives in `plan.md`.

## Final plan sections

```md
# <Title> Plan

## Summary
## Code/Request Evidence
## Stage Map and Source Status
## Decisions
## Domain Language and ADRs
## Product Plan
## Product/Design Context
- PRODUCT.md: <current/updated/created, path>
- DESIGN.md: <current/updated/created, path>
- Token/design-system owner: <path>
## UI Flow
## Visual Design
## Prototype Tech Stack
## Prototype
## Backend/Infra Tech Stack
## Vertical Slices and Task Waves
## Acceptance Criteria
## Verification Plan
## Traceability
| Requirement | Slice/task | Acceptance criteria | Verification |
|---|---|---|---|
## Artifacts
## High-Risk Controls
## Risks
## Unknowns
## Q&A
## Cleanup
```

Omit irrelevant sections; no skipped/n/a boilerplate.

## Rules

- Final plan is canonical. No required info may live only in a temp handoff/draft
- Plan cannot hand off to implementation without PRODUCT.md, DESIGN.md, and token/design-system owner evidence
- Product behavior changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner
- Do not write "see handoff"; copy the useful content into `plan.md`
- Use `modules/domain-docs.md` before writing glossary or ADR updates
- Do not put implementation decisions in `CONTEXT.md`
- Do not finish while a relevant handoff/artifact is `draft` or `blocked`
- Do not finish just because product questions are answered; unresolved `run` or
  `brief` stages need checks/proof and explicit alignment, or Plan stays blocked
- Trace requirements -> slices/tasks -> acceptance criteria -> verification
- High-risk schema/data/auth/security/deploy/stateful work needs human review,
  rollback/migration notes, telemetry/audit expectations.
- Keep evidence labels: code/docs/user quote/unknown
- Do not invent certainty
- Include file paths + localhost/device refs for artifacts
- After re-reading `plan.md`, remove absorbed temp docs: `session_state.md`,
  `plan_draft.md`, temp handoffs, empty `stages/`. Native deletion only; this
  is narrow Grill Me cleanup, not broad cleanup.
- Keep unclear/unabsorbed temp files and list why under `## Cleanup`
- Preserve artifacts: designs, prototypes, mock data, fixtures, screenshots,
  diagrams, code, and user-created docs.
- Final reply: `plan.md` path + cleanup status + next-step handoff
- Do not end with only a generic docs/config change report after writing
  `plan.md`; the user should know what can happen next.
