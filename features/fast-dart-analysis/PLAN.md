# Fast analysis in the edit loop

Status: Complete

## Outcome + scope

Pin building-flutter-apps v5.12.1 so installed Flutter projects analyze only the files they edit while fixing (Dart MCP `analyze_files`, or `dart analyze --fatal-infos <files>`) and run one package-root `dart analyze --fatal-infos` before handoff. A full or cold run took minutes per small fix. Non-goals: changing Hard Eng's `types-lint` gate, which already runs the package-root command.

## Repository context

Owners: `.agents/skill-sources/building-flutter-apps` submodule. Upstream: [building-flutter-apps v5.12.1](https://github.com/sgaabdu4/building-flutter-apps/releases/tag/v5.12.1). No Hard Eng skill or scaffold text told agents to run a full analyze after every change, so only the pin changes.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked for the skill update, the pin bump, and a merge once CI passes.

## Acceptance + steps

- [x] Submodule points at v5.12.1 (`e7a9a59`) → `git submodule status` shows it.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged main + this plan → exit 0.
Execution: One builder; submodule bump.

## Risks + recovery

An agent that trusts a cold MCP "No errors" could miss plugin lints; the skill says so and the final package-root run covers it.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `git submodule status` → `e7a9a59` (v5.12.1). `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — skill content pin; proof is the submodule revision and gate.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
