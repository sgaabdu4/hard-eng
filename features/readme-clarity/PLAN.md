# Explain Hard Eng clearly to a new reader

Status: Complete

## Outcome + scope

Rewrite the README for a solo developer building with agents. Explain proportional planning research, when Plan uses Wayfinder, Plan/Build/Ship/Learn handoffs, gates, security, setup, and lifecycle-specific enforcement in plain English. Keep claims traceable to source behavior and public documentation free of private identifiers.

## Repository context

README.md is the public entry point. Existing stage skills, gate configuration, installer, updater, hooks, and DECISION.md own the detailed behavior; describe and link to them without introducing another contract.

## Decisions + authorization

Blockers: None
The user requested the rewrite and diagrams. Reuse README.md and Mermaid's native Markdown support; no new dependency or runtime component. This small plan is required by the existing engineering workflow. Public documentation must contain no private project examples or identifiers.

## Baseline + execution

Result: Passed
Evidence: The starting source revision b77e811 passed the source gate and hosted CI. This documentation-only revision was compared against the current installer, updater, hooks, stage skills, gate contract, and report validators; its final Complete gate is tracked separately below.

## Acceptance + steps

- [x] A new reader can understand proportional research, the Wayfinder charting route, human-led/autonomous authority boundaries, and Plan/Build/Ship/Learn handoffs.
- [x] Gate, security, setup, update, and enforcement claims distinguish executable checks from instructions and host-dependent behavior.
- [x] The seven Mermaid diagrams render, local links and heading fragments resolve, and the public text contains no private paths, task identifiers, or consumer examples.

## ux_reference

N/A — repository documentation, with rendered Mermaid verification.

## Risks + recovery

Documentation could overstate hook activation, screenshot validation, security coverage, or delivery proof. Verify each claim against its executable or skill owner; retain alpha limitations and inspect the rendered diagrams for readability.

## Verification

Result: Passed
Evidence: Documentation checks passed: `git diff --check`; 31 local README links and heading fragments resolved; public-text scan found no private paths, task identifiers, consumer examples, or revision identifiers. The official Mermaid CLI rendered and visual inspection checked seven final diagrams: setup/update, plan, optional Wayfinder, build, ship, learn, and enforcement. The Wayfinder route was compared with `.agents/skills/he-plan/references/wayfinding.md`, including charting stop, one-ticket sessions, and live human verdicts for human-choice/prototype decisions. This is source/documentation verification, not proof of routing behavior. Claims were reviewed against current stage skills, `.hooks/plans.py`, `.hooks/agent_hooks.py`, `.hooks/ship_actions.py`, `.hooks/hard-eng.py`, `.hooks/gate_config.py`, `setup.py`, and `.hooks/update.py`. Source runtime code is unchanged.
E2E: N/A — repository documentation; rendered and inspected the seven native Mermaid diagrams. Product E2E is not claimed by this documentation revision.

Earlier gate: the existing native Complete gate passed 17 gates, 660 tests in 119.72 seconds, and four performance cases in 0.13 seconds for the earlier README revision. It does not verify this later documentation-only rewrite. Its first invocation correctly rejected a contradictory Complete plan with Result Pending before native checks ran; that rejected preflight is not counted as a source-test pass. This final rewrite has affected documentation proof above; no new source-suite run is claimed.

Delivery target: Merge
Delivery: Pending
