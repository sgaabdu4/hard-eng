# Orchestration module

Load after mode inference when conducting a grill-me session, resuming a draft,
closing a stage, or writing the final plan.

## Before Qs

- If user says greenfield/new app/empty repo, skip repo research and ask Q1
  immediately. Do not run CBM/context-mode/list/index/architecture first.
- For greenfield, infer code reality from the user; optionally note `greenfield
  assumed` in draft after the user answers.
- If existing code matters or user asks to modify/review existing code, ground
  the session in the actual request + repo.
- Existing code path: use CBM first (`list_projects` -> status/index ->
  architecture -> search/trace), load `modules/domain-docs.md` when domain docs
  may matter, then read relevant code/docs before asking.
- For PR/recovery sessions, `session_state.md`/`plan_draft.md` are not enough:
  check nearby `plan.md`, decision/open-question docs, and route/design docs
  before treating a question as open or final.
- For understanding/codebase-understanding requests, map current owners,
  behavior, routes, data, constraints, and unknowns before proposing a build
  path. Ask only what evidence cannot answer.
- Do not ask what code can answer. Inspect only for existing-code tasks
- Q1 must resolve the highest-impact unknown that request context cannot answer
- No evidence = `unknown`
- No codebase = do not research; ask a request-specific product/constraint Q

## Intake

Goal: build a stage map inside the inferred mode cap, not solve everything.
Ask one Q at a time.

First Q rules:
- Start from the user's concrete ask. Do not open with generic "what are we
  building?" if the ask names it.
- If a slug/title is inferable from the ask, infer it; ask only if ambiguous or
  conflicting.
- Prefer a domain/tech decision tied to the target area, e.g
  screen/route/entity/API boundary/data source/success metric.
- Generic intake Qs are allowed only when they unblock all later work and cannot
  be inferred from request/code.

Stage skipping:
- Skip sections aggressively when request + code evidence show they are
  irrelevant or already decided.
- For `skip`/`n/a`, record reason/evidence in Stage Map only; do not create a
  stage file.
- Use `brief` only when a lightweight decision record is useful; do not ask
  full-stage Qs for `brief`.
- Use `n/a` when a stage cannot apply, e.g. backend-only work has no
  UI/prototype stage.
- Use `run` only for unresolved decisions, requested artifacts, risky UX/API
  choices, or changed surfaces.

Classify only what changes routing: profile, work type, repo reality, UI need,
runtime, visual/prototype need, backend/API/data risk, certainty, desired
artifact, acceptance checks, verification, and domain-doc impact.

## Files

- Ensure `docs/planning/<slug>/`; infer slug when safe, ask only if ambiguous
- Interview writes only `session_state.md` plus `plan_draft.md`, except when the
  user explicitly asks for docs/status.
- `stage-handoff.md` owns temp stage paths; create them lazily only at stage
  close, artifact creation, user request, or final synthesis.
- Final plan is `docs/planning/<slug>/plan.md`; never write `99-final-plan.md`
- Visual/prototype modules own artifact paths and mock-data placement
- Domain docs module owns proposed `CONTEXT.md` terms and ADR candidates
- If old draft/handoff paths exist, read and absorb needed content into current
  state or `plan.md`; remove temp duplicates after verified final synthesis.
- File edits use native file tools; shell/context-mode only run or verify

## Handoff model

- Fast interview mode is default
- While asking Qs, append only the user's answer + confirmed decision to
  `plan_draft.md`; do not create/update stage handoffs.
- Create a stage handoff only when leaving a stage needs next-stage context, an
  artifact exists, risk/control detail cannot fit the draft, the user asks for
  docs/status, or final plan synthesis starts.
- Handoffs are compact summaries, not transcripts. Copy decisions, not every
  option/default.
- `skip`/`n/a` stages have no handoff
- If a handoff conflicts with user answers, ask one Q; do not silently choose
- If a module asks for many handoff details, treat that as final synthesis
  guidance. Interim max: status, decisions, blockers, artifacts, next.

## Clarification depth

- Full clarification beats speed. Ask one Q at a time for as long as needed
- Do not move stages while important unknowns remain
- A stage is clear only when needed behavior, boundaries, constraints,
  non-goals, acceptance checks, and risky edge cases are decided. Parked
  unknowns block Plan readiness.
- If an answer creates a contradiction, vague term, missing decision, or
  risk/control gap, ask another Q immediately.
- Final `plan.md` may contain unknowns only when the user explicitly says to
  leave them unknown/later.

## Stage clarity gates

Internal only. Use the active module gate. Ask until it passes or the user
explicitly blocks the unknown. Intake is clear when goal, repo reality, target
area, requested artifact, and hard constraints choose the next stage.

## Artifact depth

- Do not ask for `lite`, `build-plan`, or `full` when the request implies depth
- Honor explicit `lite`, `align`, `build-plan`, `full`, or `review`; use
  `understand` for explain/map/learn-codebase requests.
- Infer artifact depth from the conversation; gather decisions first
- Near synthesis, if the needed artifact is still unclear, ask one plain Q:
  "What should I produce next?" with options like decision summary,
  implementation plan, visual design/prototype, or full spec.
- Default to the smallest useful artifact; expand only for implementation, risk,
  or detail.

## Stage close refinement

- Refine before moving stages: convert the answer ledger into a compact summary,
  handoff, or draft section.
- Refine only after the clarity gate passes or the user explicitly parks
  remaining unknowns.
- If refinement reveals a blocker, ask one clarification Q using the terminal
  card, then refine again until resolved or parked.
- If no blocker, silently write the compact refined summary and immediately ask
  the first Q of the next stage.
- Do not paste the refined doc to the user unless they ask; just continue the
  interview.

Draft rules:
- `plan_draft.md` is an answer ledger, not a plan. Target <= 60 lines / 4 KB
- Record stage, next Q, answers, decisions, and active domain-doc notes only
- `session_state.md` owns profile, stage map, exact last/next Q, blockers,
  artifact refs, and compaction recovery
- During interview, do not store recommendations, rejected options, definitions,
  evidence, scenarios, criteria, verification, risks, or stage maps
- If too long, summarize older answers and keep asking
- Rationale belongs only in final `plan.md` or stage-close handoff

## Stage flow

Run only `run`/`brief` stages. Load the matching module, ask Qs, update
ledger/state, then refine. Artifacts write only when gates allow. Final plan
loads `modules/final-plan.md`, writes `plan.md`, and creates handoffs only for
artifact/risk traceability.

Do not create `00-intake.md` through `07-vertical-slices.md` just because a
stage is active.

## Loop

Each turn:
1. Greenfield first turn: ask Q1 immediately; no repo research/indexing. If no safe slug exists, make slug/title Q1.
2. Continuing or post-compaction: read `session_state.md`, then `plan_draft.md`, then only the active stage module.
3. If state is missing but draft exists, rebuild minimal state and mark uncertain fields `unknown`.
4. Re-ask an unanswered state Q exactly unless the latest user message answers it.
5. After an answer, update draft + state before generating the next Q.
6. If the active stage is accepted/brief/skipped, refine if needed, then advance to the next `run`/`brief` Stage Map item.
7. If existing code matters, ground with code/docs before Q1; for codebase-understanding, answer evidence-backed facts first.
8. If fuzzy terms, glossary/ADR conflicts, or doc updates matter, load `modules/domain-docs.md`.
9. If intake is incomplete, ask the highest-impact unanswered intake Q; else load only the active stage module and `modules/questions.md`.
10. Before the visible reply, persist the exact Q in `session_state.md`; visible interview reply = question only.
11. When a stage is clear, refine/handoff if needed, then continue or finalize.

## Global rules

- Never batch Qs
- Ask as many one-by-one Qs as needed; do not optimize for fewer questions
- Greenfield means question-first: no repo research, no indexing, no
  architecture scan unless user asks
- During interview, visible reply is only the next question unless user asks
- During interview, docs are `session_state.md` plus answer-ledger only. No
  per-Q handoffs. Stage map belongs in `session_state.md`, not `plan_draft.md`.
- Grill Me owns active question/state, and Impeccable Live reviews the real app
  route first. Current-design-system mocks are fallback only
- Capture UI decisions with a saved `ui-review-receipt` from the visible
  framework-native or localhost review surface
- A review answer needs an accepted durable receipt with surface kind,
  artifact/receipt paths, saved choices/components paths, exact
  question/options, selected/rejected options, chosen components, tweaks,
  evidence, and user approval
- Intake before skipping stages unless code proves n/a; after intake, skip any
  non-needed stage with evidence.
- `skip`/`n/a` stages create no stage file; final plan carries their evidence if
  needed.
- If user answers `all/both/all important`, accept when feasible; next Q asks a
  concrete behavior, boundary, or risk control.
- Visual design owns impeccable setup, PRODUCT/DESIGN context, 2-4 directions,
  user choice, tokens/components, and prototype handoff.
- Full-flow UI prototypes are token-first and atomic; keep taxonomy
  proportional and reuse components across states.
- No full-flow UI prototype before visual direction is chosen and prototype tech
  stack is decided, unless the user explicitly says to skip visual design.
- No backend/infra tech stack before product + UI flow + visual design alignment
  + approved prototype when prototype runs
- No backend/API/auth/storage/realtime integration before the mock-data prototype
  is approved
- No final plan until every `run`/`brief` stage is aligned or explicitly blocked
  If synthesis is requested early, reset to the next unresolved stage. Product
  docs do not close UI flow/visual design without accepted screen-flow/look choices.
- Final plan must be self-contained: summary, decisions, Q&A, refs, checks,
  proof, risks, unknowns, and traceability
- Do not write `99-final-plan.md`; write `plan.md` only
- Schema/data/auth/security/deploy/stateful changes require human review gate,
  rollback/migration notes, and telemetry/audit expectations.
- Surface glossary/ADR conflicts with evidence before final synthesis or plans
- Resolve parent decisions before child decisions
- Replace fuzzy terms with canonical terms
- Surface contradictions with evidence
- Within the inferred mode cap, do not stop early; skip irrelevant stages and
  continue until decisions support the requested artifact.
- Stop at the inferred mode cap. `align` may finish after options, risks, and
  validation are clear; do not drift into design/prototype/build planning unless
  the user expands scope.
- Finish only after final plan write, self-contained verification, and cleanup
  status for absorbed temp draft/handoffs.
