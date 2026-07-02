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
  green `implementation-proof`
- Learning gate: open learning or process findings route to `/he:learn`, and
  `loop-complete` requires fixed or accepted durable-owner/proof evidence
- Alignment gate: unlimited Grill Me questions until user-confirmed no-guesswork
  alignment, with no parked questions, artifacts, decisions, or unknowns before
  `/he:implement` readiness; feature/product/design/UI/ambiguous Grill Me skips
  require explicit user-approved skip evidence
- UI planning gate: Impeccable setup creates PRODUCT.md/DESIGN.md when missing;
  Grill Me UI/visual stages, accepted user-shown UI review, Impeccable Live,
  localhost current design-system proof, shared-component proof, mock-flow
  artifact, Lavish option poll receipt, saved choices/components, tweak log, and
  approval
- Safety surface: Git hooks, setup/uninstall parity, privacy scans, quality
  gates, SSOT scanner registry, vendor skill integrity, generated-asset
  freshness, and `no-mistakes`
- no-mistakes ownership: pinned upstream `/no-mistakes` skill; Hard Eng adds
  only `he-ship` integration, gate-hook repair, PR review-thread closure,
  loop-complete ship-currentness proof, and `integrations/no-mistakes`
  guardrail helpers
- Eval cadence: deterministic gates run by default; `--include-evals` is for
  skill/routing contract changes or release readiness, and
  `--include-session-evals` is for long Grill Me conversation proof
- Auto-sync safety: cron may refresh and stage upstream pin updates, but it does
  not commit or push unless `HARD_ENG_AUTO_PUSH=1` is explicitly set
- Legal surface: MIT license and README as-is/no-liability disclaimer
- Docs surface: `README.md`, `docs/project-workflow-gates.html`, generated
  README images, `PRODUCT.md`, and `DESIGN.md`

## Change Rule

Any product behavior, workflow stage, install mode, scope, caveat, or user-facing
promise change must update this file in the same plan.
