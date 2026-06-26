# Stage handoff contract

Use for module-owned temp stage artifacts.

## Purpose

A handoff is an optional compact stage summary created only at stage close, artifact creation, or final synthesis. It is not updated during normal Q&A.

Skipped/n/a stages do not get handoff files. Record their reason/evidence in the Stage Map and final plan.

## Paths

Create only when needed for a closed stage/artifact/final synthesis:

```txt
docs/planning/<slug>/stages/00-intake.md
docs/planning/<slug>/stages/01-product.md
docs/planning/<slug>/stages/02-ui-flow.md
docs/planning/<slug>/stages/03-visual-design.md
docs/planning/<slug>/stages/04-prototype-tech.md
docs/planning/<slug>/stages/05-prototype.md
docs/planning/<slug>/stages/06-backend-tech.md
docs/planning/<slug>/stages/07-vertical-slices.md
```

Do not create `99-final-plan.md`; final synthesis goes in `docs/planning/<slug>/plan.md`.

## Template

Do not create this while interviewing unless the user asks for docs/status. Use compact form at stage close. Expand only while writing final plan. At stage close, refine the answer ledger into this summary after the clarity gate passes; ask one clarification at a time if refinement finds a blocker, repeating until resolved or explicitly blocked by the user.

```md
# <Stage> Handoff

## Status
- Gate status: <draft | blocked | accepted | brief>
- Last updated: <date/session>
- Owner module: <module path>

## Decisions
- <decision> - <short reason/user answer>

## Open questions
- <question/blocker | none>

## Acceptance / verification notes
- <criterion/check | unknown>

## Risks / controls
- <risk/control | none>

## Artifacts
- <path/url/device/status | n/a>

## Next
- <what next module can assume or must ask>
```

Expanded detail allowed at gate close: inputs, definitions, domain doc notes,
ADR candidates, options considered, dependencies, traceability, high-risk
controls, gate criteria.

## Gate status rules

- `draft`: still interviewing/building
- `blocked`: needs user/code decision before next stage
- `accepted`: enough evidence/decisions for next stage
- `brief`: intentionally light; next stage can proceed with named unknowns
- `skipped`: use Stage Map entries for skipped/n/a stages, not handoff files

## Rules

- Do not update handoffs per question. During Q&A, update only `plan_draft.md` answer ledger
- Keep handoffs compact; decisions > prose; do not fill unused sections
- Use exact paths, URLs, device names, routes, states
- No hidden assumptions. Put unknowns in `Open questions`
- Before moving stages, confirm the stage is fully clarified, then refine the stage summary and set gate status
- Ask as many one-by-one clarification Qs as needed before the gate passes; do not optimize for fewer questions
- Clarification blockers: contradiction, vague term/domain conflict, missing
  required decision, unsafe risk/control gap, unclear acceptance, or
  artifact cannot be produced.
- If no blocker, do not ask extra refinement Qs; write the compact summary and continue
- `run`/`brief` stages need acceptance criteria + verification. A parked blocker
  or unknown keeps the parent Plan not-ready.
- High-risk schema/data/auth/security/deploy/stateful work needs controls before final plan
- Final plan must copy needed content into `plan.md`; no required info may live only here
- After verified final plan, remove absorbed temp handoffs. Keep only if content
  was not copied or ownership is unclear.
