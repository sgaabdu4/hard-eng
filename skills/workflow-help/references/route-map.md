# Workflow Route Map

## Core Path

Order is fixed: 1 `he-plan` -> 2 `he-implement` -> 3 `he-verify` -> 4 `he-ship` -> 5 `he-learn` when needed.
Each stage runs until its exit is true or blocked, then says `Next: ready for /he:*: yes/no`.
Prefer a fresh thread for each stage. Start the new thread with the next `/he:*` command and the `he-state.json` path from the prior receipt.
The visible command is one `he-*` command per stage. That stage loads touched-area skills, updates state, and uses parallel subagents only for independent work that can merge back through the active stage. Subagent work uses `gpt-5.5`; eval work uses `gpt-5.4-mini`.
State is required: each feature keeps an `he-state.json` in the plan/worktree. Every internal step updates `steps[]`; every required stage checklist updates `subStages[]`; every later stage records `entryGate` from the prior `PASS`; every finding from Plan onward updates `findings[]` with owner repair stage; every deterministic guard updates `guardrails[]` with owner, command, status, evidence, and whether it blocks push. Plan also records `context.product`, `context.design`, `context.tokenOwner`, and `planReadiness`. Every done or blocked step has a receipt. Before any `Next: ... yes`, run `node "$HOME/.agents/scripts/he-state.mjs" validate <he-state.json>`.
To avoid context rot, every stage exits with a receipt, not a transcript:
`Stage:` current stage; `State:` path to `he-state.json`; `Decision:` pass/blocker; `Owner/proof:` paths or commands; `Artifacts:` links/paths; `Blocker:` none or exact ask; `Next:` ready/not-ready.
Return to `he-plan` only when a finding changes scope, owner, proof path, risk route, artifact choice, or Grill Me stage map. Otherwise route the finding to its owner stage.

| Stage | When | Do | Exit |
| --- | --- | --- | --- |
| 1. Plan | New feature or unclear work starts. | Use `he-plan`. Create a Treehouse worktree before planning/coding, then run `"$HOME/.agents/scripts/ensure-worktree-ready.sh" <path>`. Run `node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all <path>`; product changes update `PRODUCT.md`, design/UI/token changes update `DESIGN.md`, and token/design-system owner paths must exist. Use `grill-me` when outcome, scope, proof, risk, UI flow, or visual direction is unclear. Let Grill Me own `session_state.md`, its stage map, and one-question loop; it asks as many one-by-one Qs as needed until aligned with no guesswork. For UI choices, inspect the design SSOT, run Grill Me UI flow/visual stages, use Impeccable Live, show a localhost current-design-system mock flow, and use Lavish only for UI option comparison and decisions through `npx -y lavish-axi poll`; save poll receipt, selected choice, rejected options, chosen components, tweaks, and user approval. Pick the lightest artifact: none, `to-prd`, `to-issues` only for missing agent-ready slices, or both. State `PASS`, `CONCERNS`, or `FAIL`. | Receipt with owner, blast radius, proof path, risk route, artifact choice, context docs, recorded findings, and `Next: ready for /he:implement: yes/no`. |
| 2. Implement | Readiness is `PASS` and code changes are needed. | Use `he-implement`. Require `entryGate.fromStage = he-plan` and `decision = PASS`. Change the canonical owner. Repeat work runs its deterministic owner first. Every violation gets lint/scanner/gate (script/test/hook/eval); duplicate-prone values or concepts also get SSOT scanner/registry coverage. Add or wire deterministic guardrails in `guardrails[]`; React/Next changes need React Doctor + Fallow audit/dupes + lint/typecheck gate, Flutter changes need package-root `dart analyze` with `flutter_skill_lints` plus tests when present. Use `codebase-design` when owner/abstraction is unclear. Add needed skills. | Receipt with root owner change, guardrail owner, proof to run, and `Next: ready for /he:verify: yes/no`. |
| 3. Verify | Implementation or review fixes changed behavior. | Use `he-verify`. Require `entryGate.fromStage = he-implement` and `decision = PASS`. Run targeted tests and use `test-quality` for test design or gap review. Run every guardrail command in `guardrails[]`; missing or failing guard routes to `he-implement`. Run `security-review` or `performance-rescue` when requested or when those risks were touched, then `thermo-nuclear-code-quality-review`, then `e2e` last when a user-visible flow changed. Auto-fix loop: diagnose failures, route code changes back through `he-implement`, update state, rerun affected proof only, repeat until clean or blocked. Loop back to Implement until tests, reviews, and required E2E are clean. | Receipt with proof, guardrail evidence, artifacts, skipped checks, gaps, and `Next: ready for /he:ship: yes/no`. |
| 4. Ship | Local verify loop is clean and work is committed. | Use `he-ship`. Require `entryGate.fromStage = he-verify` and `decision = PASS`. Run `git status --short`, then `"$HOME/.agents/scripts/ensure-worktree-ready.sh" --check --require-pre-push .`, then `node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .`, then `no-mistakes axi`; all are non-skippable ready gates. Respond to findings through the no-mistakes loop. Dry-run push only counts after project hooks are active and quality gates pass. For GitHub Actions/`gh` CI, parallelize independent logs/jobs, batch fixes locally, rerun fewest checks. | Receipt with gate status, PR/CI evidence, and either `Next: ready for /he:learn: yes` when learning findings exist or `Next: loop complete: yes` when learning is empty. |
| 5. Learn | Open `he-state.json` findings name `he-learn` as owner because a pattern repeated, review found a process gap, or a pipeline finding should harden future runs. | Use `he-learn`. Require `entryGate.fromStage = he-ship` and `decision = PASS`. Put durable learning in the narrow owner: source, script, test, hook, route map, or skill. Prefer executable checks for repeatable failures and avoid duplicating global policy. Skip this stage when learning is empty; if it runs, loop-complete requires a fixed or accepted learning finding plus durable-owner/proof sub-stages. | Receipt with future guard, owner, evidence, and `Next: loop complete: yes/no`. |

## Failure Loops

Every failed stage records a finding in `he-state.json`, loops to the owning repair stage, and retries the handoff only after owner-stage repair. Plan is re-entered only when the failure changes planning assumptions.

| Failed stage | Loop target |
| --- | --- |
| `he-plan` | Stay in `he-plan`; use `grill-me`, `codebase-design`, `to-prd`, or `to-issues` only when the missing input requires it. Grill Me asks unlimited one-by-one questions inside its active stage until aligned; parked questions, artifacts, decisions, or unknowns require `Next: ready for /he:implement: no`. |
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
- Record every failure, review finding, or planning concern in `findings[]` with the owner repair stage
- Record every deterministic script/test/lint/scanner/hook/eval in `guardrails[]` with command, status, evidence, and push-blocking status
- Record product/design context in `context`: `PRODUCT.md`, `DESIGN.md`, and token/design-system owner path. `he-plan` ready is invalid without it and a passed context-gate guardrail
- Record Grill Me/UI readiness in `planReadiness`; Plan cannot hand off without unlimited-until-aligned Grill Me evidence, no open unknowns, and accepted UI review when UI flow or visual design ran
- Record `planReadiness.uiReview.lavish` only for UI option decisions: localhost mock-flow path, no-timeout `npx -y lavish-axi poll`, poll receipt, saved choices, saved components, selected option, rejected options, and user decision
- Record `agentWork[]`; subagents must use `gpt-5.5`, evals must use `gpt-5.4-mini`
- Product behavior changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner
- `next.ready: true` is invalid while any step is pending, in progress, or blocked
- `next.ready: true` is invalid while blocking findings or push-blocking guardrails are unresolved
- `next.ready: true` is invalid without the stage-required guardrails: context/state validation for Plan, quality gate for Verify, and git status/worktree-ready/quality gate/no-mistakes for Ship
- If state validation fails, the receipt must say `Next: ready ...: no`

## Exact Specialist Routing

| Touched area | Use |
| --- | --- |
| UI/components/design polish | `atomic-ui` + `impeccable` |
| UI flow or visual decision artifact | `grill-me` with `atomic-ui` + `impeccable`; inspect existing tokens/theme/primitives/component library, create a project-local route/component/state artifact, and use Lavish only for UI option comparison and saved decisions |
| React app/Next.js | `react-doctor` + `fallow` for JS/TS health; include `fallow dupes` / clone-group checks for duplication or copy-paste; use `vercel-react-best-practices` for performance/composition |
| Flutter/Dart app | `building-flutter-apps` |
| Appwrite | `appwrite-backend` |
| Sentry/observability | `sentry-workflow` |
| Security/auth/secrets/data exposure | `security-review` |
| Performance/latency/bundles/queries | `performance-rescue` |
| PDF/deck/report artifact | `create-pdf` |
| Product video/demo | `product-demo-video` |
| Current web research or URLs | `tavily-cli` |

## Correct Course

Stop and reroute when:

- scope expands mid-implementation
- the owner or blast radius is unknown
- known repeat work skips an owner or violation lacks lint/scanner/gate
- new feature work has no Treehouse worktree
- `to-issues` is being treated as required when the accepted `plan.md` already has vertical slices or task waves
- a support tool is being treated like a workflow stage
- `no-mistakes` is being used before the local verify loop is clean and committed
- push dry-run is trusted before `ensure-worktree-ready.sh` proves project hooks
- BMAD persona/menu-code wording hides the local skill route

Reroute to `grill-me`, `to-prd`, or `to-issues` when scope is unclear or required artifacts are missing.
Create the Treehouse worktree before feature planning/coding.
Run `"$HOME/.agents/scripts/ensure-worktree-ready.sh"` after worktree creation and before `no-mistakes`.
Reroute to `codebase-design` when owner or abstraction shape is unclear.
Reroute back to Implement when tests, review, or E2E find blockers.
Reroute to `he-ship`/`no-mistakes` only after committed implementation work is ready for the gate.
