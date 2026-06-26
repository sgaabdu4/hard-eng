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
- Workflow state: `he-state.json`, stage receipts, findings, and guardrails
- Deterministic stage gates: `subStages[]`, `entryGate`, `planReadiness`,
  `agentWork`, required guardrail command identities, and non-skippable gates
- Alignment gate: unlimited Grill Me questions until user-confirmed no-guesswork
  alignment, with no parked questions, artifacts, decisions, or unknowns before
  `/he:implement` readiness
- UI planning gate: Grill Me UI/visual stages, Impeccable Live, localhost current
  design-system proof, shared-component proof, mock-flow artifact, Lavish option
  poll receipt, saved choices/components, tweak log, and approval
- Safety surface: Git hooks, setup/uninstall parity, privacy scans, quality
  gates, SSOT scanner registry, generated-asset freshness, and `no-mistakes`
- Legal surface: MIT license and README as-is/no-liability disclaimer
- Docs surface: `README.md`, `docs/project-workflow-gates.html`, generated
  README images, `PRODUCT.md`, and `DESIGN.md`

## Change Rule

Any product behavior, workflow stage, install mode, scope, caveat, or user-facing
promise change must update this file in the same plan.
