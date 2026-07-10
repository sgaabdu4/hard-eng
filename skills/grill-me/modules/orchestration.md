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

Skipping:
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

Classify only routing inputs: profile, work type, repo reality, UI need,
runtime, backend/API/data risk, certainty, artifact, acceptance, verification,
and domain-doc impact.

## Files

- Ensure `docs/planning/<slug>/` only when a session or file artifact needs it;
  infer slug when safe, ask only if ambiguous
- Interview writes only `session_state.md` plus `plan_draft.md`, except when the
  user explicitly asks for docs/status.
- `stage-handoff.md` owns temp stage paths; create them lazily only at stage
  close, artifact creation, user request, or final synthesis.
- Final plan is `docs/planning/<slug>/plan.md`; never write `99-final-plan.md`
- Visual/prototype modules own artifact paths and mock-data placement
- Domain docs module owns proposed `CONTEXT.md` terms and ADR candidates
- If old draft/handoff paths exist, read and absorb needed content into current
  state or `plan.md`; remove temp duplicates after verified final synthesis.
- File edits use native tools; shell/context-mode only run or verify

## Handoff model

- Fast interview mode is default
- While asking Qs, append only the answer + confirmed decision to
  `plan_draft.md`
- Create stage handoffs only for stage close, artifact/risk traceability, user
  docs/status requests, or final synthesis
- Handoffs are compact summaries, not transcripts
- `skip`/`n/a` stages have no handoff
- If a handoff conflicts with user answers, ask one Q; do not silently choose
- Interim max: status, decisions, blockers, artifacts, next

## Clarification depth

- Full clarification beats speed. Ask one Q at a time for as long as needed
- Do not move stages while important unknowns remain
- A stage is clear only when needed behavior, boundaries, constraints,
  non-goals, acceptance checks, and risky edges are decided
- Parked unknowns block Plan readiness
- Contradiction, vague term, missing decision, or risk/control gap -> ask the
  next Q immediately
- Final `plan.md` may contain unknowns only when the user explicitly says to
  leave them later

## Stage clarity gates

Internal only. Use the active module gate. Ask until it passes or the user
explicitly blocks the unknown. Intake is clear when goal, repo reality, target
area, requested artifact, and hard constraints choose the next stage.

## Artifact depth

- Do not ask for `lite`, `build-plan`, or `full` when the request implies depth
- Honor explicit `lite`, `align`, `build-plan`, `full`, or `review`; use
  `understand` for explain/map/learn-codebase requests.
- Infer artifact depth from the conversation; gather decisions first
- Near synthesis, if artifact shape is unclear, ask one plain Q with options:
  decision summary, implementation plan, visual design/prototype, or full spec
- Default to the smallest useful artifact

## Stage close refinement

- Before moving stages, convert the answer ledger into a compact summary,
  handoff, or draft section
- Refine only after the gate passes or the user parks unknowns
- If refinement reveals a blocker, ask one Q and refine again
- If no blocker, write the summary silently and ask the next stage's first Q
- Do not paste refined docs unless asked

Draft rules:
- `plan_draft.md` is an answer ledger, not a plan. Keep it compact; no hard cap
  that drops answers. Consolidate into final `plan.md`.
- Record stage, next Q, answers, decisions, and active domain-doc notes only
- `session_state.md` owns profile, stage map, exact last/next Q, blockers,
  artifact refs, and compaction recovery
- During interview, do not store recommendations, rejected options, definitions,
  evidence, scenarios, criteria, verification, risks, or stage maps
- If too long, summarize older answers and keep asking
- Rationale belongs only in final `plan.md` or stage-close handoff

## Stage flow

Run only `run`/`brief` stages. Load the matching module, ask Qs, update
ledger/state, then refine. Artifacts write only when gates allow. An `align` or
`lite` run may finish with an inline decision summary without `plan.md`; verify
the decision and remove temporary state after the summary is delivered. A file
artifact loads `modules/final-plan.md`, writes `plan.md`, and creates handoffs
only for artifact/risk traceability.

Do not create `00-intake.md` through `07-vertical-slices.md` just because a
stage is active.

## Loop

Each turn:
- Greenfield first turn: ask Q1 immediately; no repo research/indexing
- Resume: read `session_state.md`, then `plan_draft.md`, then active module
- Missing state + existing draft: rebuild minimal state and mark uncertain fields `unknown`
- Re-ask an unanswered state Q exactly unless the latest user message answers it
- After an answer, update draft + state before generating the next Q
- Accepted/brief/skipped stage: refine if needed, then advance to the next `run`/`brief`
- Existing code matters: ground with code/docs before Q1
- Fuzzy terms, glossary/ADR conflicts, or doc updates: load `modules/domain-docs.md`
- Intake incomplete: ask the highest-impact unanswered intake Q
- Before every visible reply, run the question-premise preflight and replace a
  stale next Q instead of trusting stored question text
- Before visible reply, persist the exact Q in `session_state.md`
- Visible interview reply = question only

## Global rules

- Never batch Qs
- Ask as many one-by-one Qs as needed; do not optimize for fewer questions
- Greenfield means question-first: no repo research/indexing unless user asks
- During interview, visible reply is only the next question unless user asks
- During interview, docs are `session_state.md` plus answer-ledger only. No
  per-Q handoffs. Stage map belongs in `session_state.md`, not `plan_draft.md`.
- Grill Me owns active question/state, and Impeccable Live reviews the real app
  route first. Current-design-system mocks are fallback only
- UI decisions need a saved `ui-review-receipt` from the visible
  framework-native or localhost surface
- Receipt needs surface kind, artifact/receipt paths, saved choices/components,
  exact question/options, selected/rejected options, chosen components, tweaks,
  `ui-presentation/v1` project-local consistency record, evidence, and user approval
- Intake before skipping stages unless code proves n/a; then skip non-needed
  stages with evidence
- `skip`/`n/a` stages create no stage file; final plan carries their evidence if
  needed.
- If user answers `all/both/all important`, accept when feasible; next Q asks a
  concrete behavior, boundary, or risk control.
- Visual design owns impeccable setup, PRODUCT/DESIGN context, 2-4 directions,
  user choice, tokens/components, and prototype handoff.
- Full-flow UI prototypes are token-first and atomic
- No full-flow UI prototype before visual direction is chosen and prototype tech
  stack is decided, unless the user explicitly says to skip visual design.
- No backend/infra tech stack before product + UI flow + visual design alignment
  + approved prototype when prototype runs
- No backend/API/auth/storage/realtime integration before mock-data prototype approval
- No final artifact until every `run`/`brief` stage is aligned or blocked. Early
  synthesis resets to the next unresolved stage. Product docs do not close UI
  flow/visual design without accepted screen-flow/look choices
- Final plan: summary, decisions, Q&A, refs, checks, proof, risks, unknowns, traceability
- Do not write `99-final-plan.md`; write `plan.md` only
- Schema/data/auth/security/deploy/stateful changes require human review gate,
  rollback/migration notes, and telemetry/audit expectations.
- Surface glossary/ADR conflicts with evidence before final synthesis or plans
- Resolve parent decisions before child decisions
- Replace fuzzy terms with canonical terms
- Surface contradictions with evidence
- Within the mode cap, do not stop early; skip irrelevant stages and continue
  until decisions support the requested artifact
- Stop at the inferred mode cap. `align` may finish after options, risks, and
  validation are clear; do not drift into design/prototype/build planning unless
  the user expands scope
- Finish after the requested artifact is delivered, self-contained verification
  passes, and temporary state cleanup is reported. Inline `align`/`lite` runs do
  not require `plan.md`; file-backed planning finishes after the final plan write.
