# Workflow Route Map

## Canonical Router Handshake

Use this handshake for every non-trivial request. Tiny factual answers and
simple shell-command requests can take the direct route, but still load the
matching specialist skill when one clearly applies.

1. Route first: classify the lightest route that can produce the needed proof.
2. Check onboarding gaps: goal, repo/project, constraints, risk, proof, branch
   or worktree, and what "done" means. Do not ask for facts the repo or tools
   can answer.
3. Read evidence before discussion: inspect local code, docs, config, diffs,
   state files, and existing artifacts; use `research` plus web/search for
   current external facts, official docs, APIs, standards, or source URLs.
4. Ask discussion questions only when evidence leaves a blocking choice. Use
   `grill-me` in `align`/`lite` mode for normal decisions and one clear
   question at a time for unclear work.
5. Return a route receipt before build: route, evidence read, decisions made,
   rejected routes, open unknowns or next question, next skill or `/he:*`
   command, proof required, and what not to run.
6. Execute the chosen route only after the receipt is clear: direct answer,
   direct skill, normal decision, small change, or full Hard Eng.

The handshake does not force Hard Eng. It prevents guessing before either the
small route or the heavy route starts.

## Routing Decision

Choose the lightest route that can produce the needed proof:

| Route | Use when | Next |
| --- | --- | --- |
| Direct answer | The user asks a factual/code explanation or asks to run a simple command. | Answer or run the command; no workflow wrapper. |
| Direct skill | The task clearly matches a specialist skill and does not need the Hard Eng state loop. | Load that skill and do the work. |
| Small change | The requested edit has a clear owner, low blast radius, known proof, and no unresolved product/design/security/data-risk decision. | Read evidence, make the scoped change, run checks sized to the change, and report proof. |
| Normal decision | The user wants alignment, tradeoffs, approach, options, or a plan without the full shipping gate. | Use `grill-me` in `align`/`lite` mode. Produce an inline decision or `docs/planning/<slug>/plan.md` only when useful. |
| Hard Eng | The user asks for `/he:*`, serious feature work, risky implementation, PR/shipping discipline, or no-mistakes loop readiness. | Use the Hard Eng path below. |

Normal decisions do not require Treehouse, `he-state.json`, stage receipts, or
no-mistakes. Escalate a normal decision into Hard Eng only when the user asks
for the HE loop, implementation/shipping risk appears, or the decision becomes
feature work that needs stateful proof.

For planning artifacts, `plan.md` is canonical. It absorbs PRD/spec content,
vertical slices, task waves, blocking edges, frontier, acceptance criteria,
verification, and risks. Do not route to separate PRD/spec/ticket skills for
Hard Eng planning.

## Router Rules

- `codebase-memory`, `context-mode`, and `terse` are support tools, not stages
- Route by task and risk, not by persona names or BMAD menu codes
- Do not ask onboarding questions when local evidence can answer them
- Do not skip research/evidence reading for code, config, dependency, API,
  current-doc, or repo-policy decisions
- Any request to build, code, or implement a feature needs a readiness gate
  before editing: clear outcome, owner, blast radius, proof path, and risk
  route. If those are weak, return `CONCERNS`/`FAIL` for Hard Eng or route to
  `grill-me` for the next blocking question; do not start coding.
- If the request is a normal decision, use `grill-me` in `align`/`lite` mode;
  do not require `he-plan`, Treehouse, `he-state.json`, or no-mistakes
- If the request is ambiguous, send it to `grill-me`; escalate to `he-plan`
  only when the user wants the full Hard Eng loop or the work is risky enough
  to need stateful shipping gates
- If a feature is ready to build, require a branch or Treehouse worktree before
  implementation
- If readiness is weak, return `CONCERNS` or `FAIL` and name the missing input
- At stage exit, use the receipt format from this file; no transcript dump
- For shipping work, end at `he-ship`/`no-mistakes`, not direct push, unless
  the user explicitly overrides the local gate

## Hard Eng Path

Order is fixed: 1 `he-plan` -> 2 `he-implement` -> 3 `he-verify` -> 4 `he-ship` -> 5 `he-learn` when needed.
Each stage runs until its exit is true or blocked, then says `Next: ready for /he:*: yes/no`.
Prefer a fresh thread for each stage. Start the new thread with the handover prompt from the prior receipt; it must include the next `/he:*` command, worktree path, `he-state.json` path, stage, state, next target, blockers, artifacts, and the instruction to read state first.
The visible command is one `he-*` command per stage. That stage loads touched-area skills, updates state, and uses parallel subagents only for independent work that can merge back through the active stage. Subagent work uses `gpt-5.5`; eval work uses `gpt-5.6-luna`. Delegated work is not fire-and-forget: `agentWork[]` records status, progress, last-progress time, recovery prompt, required reason, and evidence so the parent can tell running, stalled, blocked, failed, and done apart.
State is required: each feature keeps an `he-state.json` in the plan/worktree. Every internal step updates `steps[]`; every required stage checklist updates `subStages[]`; every later stage records `entryGate` from the prior `PASS`; every finding from Plan onward updates `findings[]` with owner repair stage; every repeated miss, review gap, process gap, or missing future guard becomes a learning finding with `ownerStage: he-learn` and `repairType: learning`; every deterministic guard updates `guardrails[]` with owner, command, status, evidence, and whether it blocks push. Stages 2-4 also record `guardrailInventory.touchedStacks[]` and `guardrailInventory.requiredGuardrails[]` so normalized touched-stack guards are either required with a `guardrails[]` entry or not applicable with reason/evidence. E2E approval boundaries live in `approvalBoundaries[]` with `id`, `category`, `status`, `reason`, and `evidence[]`; categories are `prod-backend-write`, `prod-cleanup`, `native-permission`, `real-credentials`, and `generated-credentials`. Repeated user-caught misses live in `repeatMisses[]` with `issueClass` and `evidence[]`; any user-caught workflow/process miss in findings, decisions, or blockers needs matching `repeatMisses[]` or `he-learn` learning/process evidence before ready. Plan also records `context.product`, `context.design`, `context.tokenOwner`, and `planReadiness`; `planReadiness.grillMe` is readiness metadata only, while `session_state.md`/`plan_draft.md` own the interview ledger and final `plan.md` absorbs it. Every later ready handoff preserves and revalidates `planReadiness`. Every done or blocked step has a receipt; only a final receipt with `decision: PASS` can set `Next: ... yes`. Before any `Next: ... yes`, run `node "$HOME/.agents/scripts/he-state.mjs" validate <he-state.json>`.
To avoid context rot, every stage exits with a receipt, not a transcript:
`Stage:` current stage; `State:` path to `he-state.json`; `Decision:` pass/blocker; `Owner/proof:` paths or commands; `Artifacts:` links/paths; `Blocker:` none or exact ask; `Next:` ready/not-ready; `Handover prompt:` copy-paste prompt for a brand-new session with worktree, state, blockers, artifacts, and next `/he:*` command.
Vendored upstream skills are canonical and read-only. Do not edit `vendor/skill-upstreams/**` or symlinked upstream skill text; change the local wrapper, route-map, integration, hook, or eval that calls the upstream skill. Submodule gitlink updates or deletions are allowed vendor changes; repo-owned files under `vendor/skill-upstreams/**`, including gitlinks replaced by regular files, fail integrity checks.
Return to `he-plan` only when a finding changes scope, owner, proof path, risk route, artifact choice, or Grill Me stage map. Otherwise route the finding to its owner stage.

| Stage | When | Do | Exit |
| --- | --- | --- | --- |
| 1. Plan | Full Hard Eng feature/risky shipping work starts. | Use `he-plan`. Create a Treehouse worktree before planning/coding, then run `"$HOME/.agents/scripts/ensure-worktree-ready.sh" <path>`. Run `node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all <path>`; product changes update `PRODUCT.md`, design/UI/token changes update `DESIGN.md`, and token/design-system owner paths must exist. If they are missing, run Impeccable setup first: `/impeccable init` for PRODUCT.md and `/impeccable document` for DESIGN.md. Use `grill-me` when outcome, scope, proof, risk, UI flow, or visual direction is unclear. Also use it when slices, blocking edges, or frontier are unclear. Let Grill Me own `session_state.md`, its stage map, and one-question loop; `plan_draft.md` is its answer ledger; it asks as many one-by-one Qs as needed until aligned with no guesswork. Keep `planReadiness.grillMe` to readiness metadata only: required/status, state path, question policy, alignment/open blockers, stage statuses, current visible asked question when unresolved, and artifact paths. If feature/product/design/UI/ambiguous work skips Grill Me, record explicit user-approved skip evidence. For UI choices, inspect the design SSOT, run Grill Me UI flow/visual stages, use Impeccable Live on the real app route with current tokens/components first, use a current-design-system mock only when the real surface cannot exist yet, and save a `ui-review-receipt` from the real or fallback review surface; record accepted UI review evidence, exact question/options, selected choice, rejected options, chosen components, tweaks, screenshot paths, user-visible proof that screenshots or visual artifacts were shown before acceptance, and user approval. Final `plan.md` is the only required planning artifact and must include the spec, accepted vertical slices/task waves, blocking edges/frontier, acceptance criteria, verification, and risks needed for implementation readiness. State `PASS`, `CONCERNS`, or `FAIL`; only `PASS` can hand off to `/he:implement`, and `CONCERNS`/`FAIL` must say ready no. User-answerable blockers ask the next visible Grill Me question instead of parking concerns. | Receipt with owner, blast radius, proof path, risk route, plan path, context docs, recorded findings, and `Next: ready for /he:implement: yes/no`. |
| 2. Implement | Readiness is `PASS` and code changes are needed. | Use `he-implement`. Require `entryGate.fromStage = he-plan` and `decision = PASS`. Complete `ssot-owner-reuse` before `test-first` and before owner changes: search shared/peer components, similar screens, interaction/domain owners, duplicate/clone groups, tokens/theme, and record reuse/extend/create/not-applicable decisions. Load `test-quality`, list behavior scenarios, add or identify the smallest failing test first, record the red state as `test-first-proof` with explicit `test-quality` scenario or review evidence and ordered `sequence` before `owner-change`, then change the canonical owner. If red-first is impossible, run mutation/"make it fail" proof before readying Verify. Record the targeted green or post-change test proof as `implementation-proof` with a later ordered `sequence`. For UI-touched work, capture actual implementation screenshots from the real route/surface after `implementation-proof` and record a passed `implementation-ui-screenshots` guardrail before readying Verify, with an ordered `sequence` after `owner-change` and `implementation-proof`; this is required real UI proof and cannot be replaced by unit tests, curl, or command-only evidence. Run `find-deterministic-owner.mjs --json` and record `deterministic-owner-scan` before fresh reasoning. Repeat work runs its deterministic owner first. Every violation gets lint/scanner/gate (script/test/hook/eval); duplicate-prone values or concepts also get SSOT scanner/registry coverage. Add or wire deterministic guardrails in `guardrails[]`; React/Next changes need React Doctor + Fallow audit/dupes + lint/typecheck gate with positive typecheck pass/result evidence, Flutter changes need package-root `dart analyze` with `flutter_skill_lints` plus tests. Use `codebase-design` when owner/abstraction is unclear. Add needed skills and learning findings for repeated misses or future guards. | Receipt with root owner change, SSOT reused/extended/new-owner summary, TDD proof, implementation proof, UI screenshots when applicable, guardrail owner, proof to run, learning findings or no-learning evidence, and `Next: ready for /he:verify: yes/no`. |
| 3. Verify | Implementation or review fixes changed behavior. | Use `he-verify`. Require `entryGate.fromStage = he-implement` and `decision = PASS`. Run targeted tests and use `test-quality` for test design or gap review. Run every guardrail command in `guardrails[]`; missing or failing guard routes to `he-implement`. Run `check-project-quality-gates.mjs --require-push-gate .` so every detected supported project root has test, lint/static-check, and format coverage. Do not start E2E while UI SSOT compliance is unresolved or disputed. Run `security-review` or `performance-rescue` when requested or when those risks were touched, then `thermo-nuclear-code-quality-review`, then `e2e` last when a user-visible flow changed. Auto-fix loop: diagnose failures, route code changes back through `he-implement`, update state, rerun affected proof only, repeat until clean or blocked. Loop back to Implement until tests, reviews, and required E2E are clean. | Receipt with proof, guardrail evidence, artifacts, skipped checks, gaps, and `Next: ready for /he:ship: yes/no`. |
| 4. Ship | Local verify loop is clean and work is committed. | Use `he-ship`. Require `entryGate.fromStage = he-verify` and `decision = PASS`. Run `git status --short`, then `"$HOME/.agents/scripts/ensure-worktree-ready.sh" --check --require-pre-push .`, then `node "$HOME/.agents/scripts/format-hard-eng.mjs" --check .`, then `node "$HOME/.agents/scripts/check-no-mistakes-projects.mjs" .`, then `node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .`, then `no-mistakes axi run --intent ...`; all are non-skippable ready gates. Respond to findings through the no-mistakes loop. Run PR evidence repair after the latest no-mistakes run, then `repair-pr-evidence.mjs --check-review-threads` after Copilot or human review has had a chance to run; unresolved actionable threads route back to the right stage before loop-complete. After final CI proof, record a `ship-currentness` guardrail using `git rev-parse HEAD && git status --short` with validated head and clean worktree evidence, then run `node "$HOME/.agents/scripts/he-state.mjs" validate --live-currentness --repo . he-state.json` before loop-complete so the state is checked against real `HEAD` and parsed dirty scope. Dry-run push only counts after project hooks are active and quality gates pass. For GitHub Actions/`gh` CI, parallelize independent logs/jobs, batch fixes locally, rerun fewest checks. | Receipt with gate status, PR/CI evidence, review-thread evidence, loop-complete currentness evidence when applicable, and either `Next: ready for /he:learn: yes` when open learning findings exist or `Next: loop complete: yes` only when learning is empty. |
| 5. Learn | Open `he-state.json` findings name `he-learn` as owner because a pattern repeated, review found a process gap, or a pipeline finding should harden future runs. | Use `he-learn`. Require `entryGate.fromStage = he-ship` and `decision = PASS`. Put durable learning in the narrow owner: source, script, test, hook, route map, or skill. Prefer executable checks for repeatable failures and avoid duplicating global policy. Skip this stage when learning is empty; if it runs, loop-complete requires a fixed or accepted learning finding plus durable-owner/proof sub-stages. | Receipt with future guard, owner, evidence, and `Next: loop complete: yes/no`. |

## Failure Loops

Every failed stage records a finding in `he-state.json`, loops to the owning repair stage, and retries the handoff only after owner-stage repair. Plan is re-entered only when the failure changes planning assumptions.

| Failed stage | Loop target |
| --- | --- |
| `he-plan` | Stay in `he-plan`; use `grill-me` or `codebase-design` only when the missing input requires it. Grill Me asks unlimited one-by-one questions inside its active stage until aligned; parked questions, artifacts, decisions, slices, blocking edges, frontier, or unknowns require `Next: ready for /he:implement: no`. If the blocker is user-answerable, ask the next visible Grill Me question instead of using `CONCERNS` as a parking lot. |
| `he-implement` | Return to `he-plan` if owner/scope changed; otherwise stay in `he-implement` and repair the owner path. |
| `he-verify` | Return fixes through `he-implement`, then rerun only affected proof. |
| `he-ship` | Use the no-mistakes response loop; code changes return through `he-implement`, proof gaps through `he-verify`, gate/evidence fixes stay in `he-ship`. |
| `he-learn` | Stay in `he-learn` until the durable guard owner exists and passes. |

## HE Entry Points

`/he:plan` is human shorthand for `he-plan`; Codex skill names stay hyphenated.

| Shorthand | Skill | Owns |
| --- | --- | --- |
| `/he:plan` | `he-plan` | Stage 1. Ends by saying if `/he:implement` is ready. |
| `/he:implement` | `he-implement` | Stage 2. Ends by saying if `/he:verify` is ready. |
| `/he:verify` | `he-verify` | Stage 3. Ends by saying if `/he:ship` is ready. |
| `/he:ship` | `he-ship` | Stage 4. Ends by saying if `/he:learn` is needed or if the loop is complete. |
| `/he:learn` | `he-learn` | Stage 5. Runs only when state contains an open learning finding. |

## Stateful Steps

- Use `node "$HOME/.agents/scripts/he-state.mjs" template` when a feature has no state file
- Treat `he-state.json` as the resume source of truth; the chat transcript is not authoritative
- New stage threads read `he-state.json` first; they do not need the previous chat transcript
- Update state before and after each internal step, not only at stage end
- Record every required stage checklist item in `subStages[]`; skipped items need reason and evidence, and non-skippable gates must be done
- Record `entryGate` for stages 2-5; the prior stage must be `PASS`
- Record every failure, review finding, or planning concern in `findings[]` with the owner repair stage; when the issue is repeated, procedural, or needs a future guard, also record an open learning finding for `he-learn`
- Record every deterministic script/test/lint/scanner/hook/eval in `guardrails[]` with command, status, evidence, ordered `sequence` when required, and push-blocking status; record regex scanners, Git hooks, lint/analyze/typecheck, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention in `guardrailInventory.requiredGuardrails[]`
- Record product/design context in `context`: `PRODUCT.md`, `DESIGN.md`, and token/design-system owner path. `he-plan` ready is invalid without it and a passed context-gate guardrail
- Record `ssot-owner-reuse` before `test-first` and `owner-change`; `ownerLedger[]` covers owner classes implied by `guardrailInventory.touchedStacks[]`; UI/component work must prove component-pattern owner search before SSOT scanner `not_applicable`, JS/TS duplicate risk must prove Fallow evidence, React/Next must prove positive typecheck pass/result evidence, and other stacks need tool-absence plus explicit no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision; touched stacks normalize path segments, camel/PascalCase names, file extensions, separators, and plurals
- Record E2E approval boundaries for real/generated credentials, native permission prompts, affirmative prod/backend/Appwrite/DB/payment/email/SMS/sharing side effects, backend permission/schema/index changes, and cleanup before any ready handoff with matching policy or risky guardrail, step, or non-eval agent-work evidence, including mixed evidence that also mentions cleanup or prevention; matching required boundaries must be `status: approved` with affirmative human approval proof; credential boundaries need `redactedCredentialRef` and `dataScope`, generated credentials need positive `cleanupProof[]`, and distinct production side effects need matching `sideEffectKey` or equivalent proof; postposed negation such as `production SMS not sent` stays non-risk
- Record Grill Me/UI readiness in `planReadiness`; keep `planReadiness.grillMe` to readiness metadata only and do not duplicate every Grill Me Q/A or answer ledger. `next.ready: true` is invalid without unlimited-until-aligned Grill Me evidence, no open unknowns, explicit user-approved Grill Me skip evidence when feature/product/design/UI/ambiguous work bypasses Grill Me, and accepted required UI review with review surface, user response, design-system/shared-component evidence, and no open decisions or unknowns
- Record `planReadiness.uiReview.receipt` only for UI option decisions: accepted status, `surfaceKind` (`real-route`, `react-localhost`, `storybook`, `flutter-widget-preview`, `widgetbook`, `simulator`, or `local-html`), artifact path, receipt path, saved choices/components paths, exact question/options, selected/rejected options, chosen components, screenshot paths, user-visible evidence that screenshots or visual artifacts were shown before acceptance, evidence, and user decision. Browser surfaces need localhost `surfaceUrl`; simulator needs `deviceTarget`; Flutter Widget Previewer/Widgetbook need localhost `surfaceUrl` or `deviceTarget`
- Record `agentWork[]`; subagents must use `gpt-5.5`, evals must use `gpt-5.6-luna`; running, stalled, blocked, or failed entries need `progress[]`, `lastProgressAt`, and `recoveryPrompt`, with `reason` for stalled or blocked work
- Preserve completed `gpt-5.4-mini` eval evidence only when `status` is `done` and `completedAt` predates `2026-07-09T22:55:58.000Z`; this historical compatibility does not permit new legacy-model eval work
- Eval cadence is realistic: deterministic state/hooks/scanners run by default; `gpt-5.6-luna` model evals run only for skill/routing contract changes, release readiness, or a regression; he-plan readiness regressions are covered by that eval lane. Long Grill Me session evals run only for conversation-behavior changes or release proof
- Product behavior changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner
- `next.ready: true` is invalid while any step is pending, in progress, or blocked, or while `agentWork[]` is planned, running, stalled, failed, or blocked
- `next.ready: true` is invalid while blocking findings or push-blocking guardrails are unresolved
- `next.ready: true` is invalid without the stage-required guardrails: context/state validation for Plan, ordered TDD `test-first-proof` with explicit `test-quality` evidence, green `implementation-proof`, and touched-stack inventory for Implement, quality gate for Verify, git status/worktree-ready/format-check/project-inventory/quality gate/no-mistakes for Ship, and `ship-currentness` for Ship loop-complete
- `he-implement` ready is invalid for UI-touched work without an `implementation-ui-screenshots` guardrail containing actual implementation screenshot paths captured before `/he:verify`, with ordered `sequence` evidence after `owner-change` and `implementation-proof`
- Ship must record a `ship-currentness` guardrail using `git rev-parse HEAD && git status --short` with validated head and clean worktree evidence before loop-complete
- `next.ready: true` is invalid when user-caught workflow/process misses in findings, decisions, or blockers lack matching `repeatMisses[]` or `he-learn` learning/process evidence
- `next.ready: true` is invalid when normalized `repeatMisses[]` issue classes show the same class twice without an exact `/he:learn` finding match
- `loop-complete` is invalid while open learning findings exist; route to `/he:learn` instead
- If state validation fails, the receipt must say `Next: ready ...: no`

## Exact Specialist Routing

| Touched area | Use |
| --- | --- |
| Workflow route, next step, normal decision vs Hard Eng, or direct skill choice | `workflow-help` |
| Router onboarding gaps, evidence-first route choice, decision receipt, or small-change vs HE split | `workflow-help` |
| Normal decision, approach, tradeoff, alignment, or lightweight plan | `grill-me` in `align`/`lite` mode; no HE state unless escalated |
| Foggy scope, too many possible routes, unclear first slice, or unclear blocking edge/frontier | `workflow-help`, then `grill-me` or `he-plan` based on whether the user wants direct planning or the full HE loop |
| Primary-source research synthesis, docs/API fact checks, or cited notes | `research` + available web/search tools |
| Skill writing, skill audits, trigger design, pruning, or splitting | `writing-great-skills` |
| UI/components/design polish | `atomic-ui` + `impeccable` |
| UI flow or visual decision artifact | `grill-me` with `atomic-ui` + `impeccable`; inspect existing tokens/theme/primitives/component library, create a project-local route/component/state artifact, and save a `ui-review-receipt` from the real or fallback review surface |
| React app/Next.js | `react-doctor` + `fallow` for JS/TS health; include `fallow dupes` / clone-group checks for duplication or copy-paste with result evidence, lint, and positive typecheck pass/result evidence; use `vercel-react-best-practices` for performance/composition |
| Flutter/Dart app | `building-flutter-apps` |
| Appwrite | `appwrite-backend` |
| Sentry/observability/issues/setup | `sentry-workflow` only; do not expose `sentry-sdk-setup`, `sentry-feature-setup`, or `sentry-cli` as the user-facing route |
| Security/auth/secrets/data exposure | `security-review` |
| Performance/latency/bundles/queries | `performance-rescue` |
| PDF/deck/report artifact | `create-pdf` |
| Product video/demo | `product-demo-video` |
| Direct web search, extraction, crawl, or URL discovery | available web/search tools |
| Existing reusable skill search | `find-skills` |

## Direct Skill Routing

Use these when the user asks for the specific workflow, or when they are a
better fit than a Hard Eng stage:

| Need | Use |
| --- | --- |
| Huge unclear effort that needs destination/fog/frontier mapping | `grill-me`; final `plan.md` owns destination, decisions so far, fog, frontier, and blocking edges |
| Current conversation should become a spec, PRD, or implementation brief | `grill-me` final synthesis; write or update `plan.md` |
| Spec or plan should become tracer-bullet tickets | `grill-me` vertical-slices/final-plan modules; keep slices in `plan.md` unless the user explicitly asks for tracker publishing |
| Build a concrete behavior test-first outside full Hard Eng | `tdd` + `test-quality` |
| Review a branch, PR, or WIP diff against standards and spec | `code-review` + `thermo-nuclear-code-quality-review` |
| Triage raw incoming bugs or feature requests into agent-ready work | `triage` |
| Preserve context across a fresh session | `handoff` |
| Answer a design question with throwaway code | `prototype` |
| Maintain domain terms, context docs, or ADRs | `domain-modeling` |
| Improve module depth/codebase architecture | `improve-codebase-architecture` + `codebase-design` |
| Set up repo tracker config, triage labels, domain docs, or repo agent-skill onboarding | `setup-engineering-skills` |
| Set up local pre-commit tooling by request | `setup-pre-commit` |
| Learn a concept statefully over sessions | `teach` |

## Skill Quality

Use `writing-great-skills` before creating, auditing, splitting, pruning, or optimizing local skills. Keep trigger files short, put branch-specific material in `references/*.md`, and add route/eval coverage when a new skill becomes active.

External skill-writing concepts adopted here:

- Trigger: description text should name real invocation branches, not body details
- Structure: `SKILL.md` should hold only always-needed steps and pointers
- Steering: use strong leading words and checkable completion criteria
- Pruning: delete no-ops, sediment, duplication, and negation-heavy guidance
- Research: prefer primary sources and cited notes before implementation when facts are current or external

## Correct Course

Stop and reroute when:

- scope expands mid-implementation
- the owner or blast radius is unknown
- known repeat work skips an owner or violation lacks lint/scanner/gate
- new feature work has no Treehouse worktree
- a separate spec/ticket skill is being treated as required when `plan.md` should own the planning content
- a support tool is being treated like a workflow stage
- `no-mistakes` is being used before the local verify loop is clean and committed
- Ship is marked loop-complete while known Copilot or human review threads are unresolved or unread
- Ship is marked loop-complete without final `ship-currentness` after CI proof
- push dry-run is trusted before `ensure-worktree-ready.sh` proves project hooks
- BMAD persona/menu-code wording hides the local skill route

Reroute to `grill-me` when scope, slices, blocking edges, frontier, or required plan content are missing.
Create the Treehouse worktree before feature planning/coding.
Run `"$HOME/.agents/scripts/ensure-worktree-ready.sh"` after worktree creation and before `no-mistakes`.
Reroute to `codebase-design` when owner or abstraction shape is unclear.
Reroute back to Implement when tests, review, or E2E find blockers.
Reroute to `he-ship`/`no-mistakes` only after committed implementation work is ready for the gate.
