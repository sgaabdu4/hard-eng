# Hard Eng Product

## Purpose

Hard Eng is a local, stateful engineering workflow for coding agents. It gives a
machine one shared rule, skill, hook, MCP, and verification surface, then routes
feature work through `/he:plan`, `/he:implement`, `/he:verify`, `/he:ship`, and
`/he:learn`.

## Users

Primary users are engineers running Codex on macOS who want agent work to survive
context changes, use deterministic guardrails, and ship through repeatable local
and CI gates.

## Canonical Routing Ownership

- `workflow-help` is the front door for every non-trivial request. It selects a
  direct answer, direct skill, small change, normal decision, or full Hard Eng
  route from evidence and risk.
- Full Hard Eng work follows `/he:plan` → `/he:implement` → `/he:verify` →
  `/he:ship` → `/he:learn` when learning findings exist. Each stage-specific
  reference owns its detailed contract; the router owns selection and shared
  invariants.
- Grill Me owns alignment and final `plan.md` synthesis. `plan.md` owns PRD/spec
  content, vertical slices, task waves, blockers, frontier, acceptance criteria,
  and verification. Retired `to-prd` and `to-spec` route to that owner; retired
  `to-issues` and `to-tickets` route to accepted slices.
- Separate tracker cards are optional and created only on explicit request;
  Grill Me's tracker-publishing reference owns their format and uses
  `docs/agents/issue-tracker.md` when that project contract exists.
- UI prototypes route through `prototype`, `atomic-ui`, and `impeccable`;
  variant selection and prototype routes remain inaccessible in production.

## Product Surface

- Maturity/version: pre-1.0 alpha; [VERSION](VERSION) owns the current release
  string and Git tags use `vMAJOR.MINOR.PATCH` with prerelease suffixes before
  `v1.0.0`
- Install modes: `--full`, `--skills-only`, `--prereqs-only`, `--uninstall`
- Skill selection: `--full` installs every local Hard Eng skill; interactive setup
  and `--skills-only` can persist `all`, `none`, or a named local skill subset
  in `~/.config/hard-eng/skills.json`
- Workflow state: `he-state.json`, stage receipts, handover prompts, findings,
  and guardrails
- Deterministic stage gates: `subStages[]`, `entryGate`, `planReadiness`,
  `agentWork`, required guardrail command identities, Ship loop-complete
  currentness proof, and non-skippable gates
- Subagent lifecycle: `agentWork[]` records delegated work status, progress,
  last-progress time, stall/blocker reason, and a recovery prompt before any
  ready handoff can pass
- Implement proof gate: ordered `test-first` and explicit `test-quality` backed
  red-first or mutation `test-first-proof` before `owner-change`, followed by
  green `implementation-proof`; UI-touched work also requires actual
  implementation screenshots from the real route/surface after implementation
  proof and before `/he:verify`
- Learning gate: open learning or process findings route to `/he:learn`, and
  `loop-complete` requires fixed or accepted durable-owner/proof evidence
- Alignment gate: unlimited Grill Me questions until user-confirmed no-guesswork
  alignment, with no parked questions, artifacts, decisions, or unknowns before
  `/he:implement` readiness; `he-state.json.planReadiness.grillMe` stores
  readiness metadata only while `session_state.md`/`plan_draft.md` own the
  interview ledger and final `plan.md` absorbs it; user-answerable blockers
  require the next visible Grill Me question instead of a parked `CONCERNS`
  exit; feature/product/design/UI/ambiguous Grill Me skips require explicit
  user-approved skip evidence
- UI planning gate: Impeccable setup creates PRODUCT.md/DESIGN.md when missing;
  Grill Me UI/visual stages, accepted user-shown UI review, Impeccable Live,
  framework-native or localhost current design-system proof, shared-component
  proof, mock-flow artifact when needed, saved UI review receipt, saved
  choices/components, screenshot paths for every shown option, user-visible
  screenshot evidence, tweak log, and approval
- Safety surface: Git hooks, setup/uninstall parity, privacy scans, quality
  gates, deterministic formatting, per-project `.no-mistakes.yaml` inventory,
  SSOT scanner registry, vendor skill integrity, generated-asset freshness,
  hard-eng artifact hygiene, write-safety scanners, and `no-mistakes`
- no-mistakes ownership: pinned upstream `/no-mistakes` skill; Hard Eng owns
  the global skill link and an `init`-isolating command wrapper refreshed by
  the installer, wrapper-preserving auto-update, stale Codex agent-path repair
  that preserves executable overrides, and restored only when an upstream
  binary exists, while upstream owns the binary and configured state home. Hard
  Eng adds only `he-ship` integration, wrapper preflight for `axi run`/`rerun`,
  deterministic per-root `commands.test`, `commands.lint`, and
  `commands.format` checks, per-project `.no-mistakes.yaml` inventory, gate-hook
  repair, PR review-thread closure, loop-complete ship-currentness proof, the
  `no-mistakes-required` current-head PR check with its same-repo maintainer
  submodule-only exemption, and `integrations/no-mistakes` guardrail helpers
- Eval cadence: deterministic gates run by default; `--include-evals` is for
  skill/routing contract changes, he-plan readiness regressions, or release
  readiness, and `--include-session-evals` is for long Grill Me conversation
  proof. New eval work uses `gpt-5.6-luna`; completed `gpt-5.4-mini` state
  evidence remains valid only when its `completedAt` predates
  `2026-07-09T22:55:58.000Z`
- Auto-sync safety: cron may refresh and stage upstream pin updates, but it does
  not commit or push unless `HARD_ENG_AUTO_PUSH=1` is explicitly set
- Legal surface: MIT license, included third-party notices, and README
  as-is/no-liability disclaimer
- Docs surface: `README.md`, `docs/project-workflow-gates.html`, generated
  README images, `PRODUCT.md`, and `DESIGN.md`

## Change Rule

Any product behavior, workflow stage, install mode, scope, caveat, or user-facing
promise change must update this file in the same plan.
