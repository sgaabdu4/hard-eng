---
name: he-implement
description: Use for /he:implement; owner-first implementation after PASS with TDD, deterministic owner reuse, and guardrails.
---

# he-implement

Stage 2/5. Use `/he:implement` only after `he-plan` is `PASS`. Finish the owner change; do not timebox it.

Read `../workflow-help/references/route-map.md` and `../test-quality/SKILL.md` before acting, then load touched-area skills only.

## Contract

- Update `he-state.json` before/after each internal step; record findings in `findings[]`; validate it before any ready-yes handoff
- Record every Implement sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before readying Verify
- Require owner, blast radius, proof path, and risk route; missing shape -> `he-plan` or `codebase-design`
- Change the canonical owner, not a wrapper, fallback, mode flag, or duplicate path
- Before `owner-change`, use `test-quality` and follow `references/tdd-proof.md`; red-first or mutation/"make it fail" proof is required before readying Verify
- Run `node "$HOME/.agents/scripts/find-deterministic-owner.mjs" --json --root <repo> <target>` before fresh reasoning; record it as `deterministic-owner-scan` in `guardrails[]`
- Record TDD proof as `test-first` in `subStages[]` and `test-first-proof` in `guardrails[]` with command/evidence showing explicit `test-quality` use plus `red-first`, `failing test`, `failed as expected`, `mutation`, or `make it fail`; both need ordered `sequence` before `owner-change`
- After `owner-change`, record the targeted green or post-change test proof as `implementation-proof` in `guardrails[]` with a later ordered `sequence`
- Run matching deterministic owners first; violations leave lint/scanner/gate coverage in `guardrails[]`, plus SSOT scanner/registry coverage when duplicated values, commands, tokens, or policy concepts could drift
- Record touched-stack guardrail coverage in `guardrailInventory.requiredGuardrails[]`: regex scanners, Git hooks, lint/analyze/typecheck, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention are `required` with a matching `guardrails[]` entry or `not_applicable` with reason/evidence
- For React/Next, wire React Doctor, Fallow audit/dupes, lint, and typecheck into a deterministic script or pre-push hook. For Flutter, wire package-root `dart analyze` with `flutter_skill_lints` and tests when present
- Record repeated misses, review gaps, process gaps, or missing future guardrails as `findings[]` with `ownerStage: he-learn`, `repairType: learning`, and owner evidence; record no-learning-needed as the `learning-capture` sub-stage with reason/evidence
- Run `node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .` when adding or reviewing push-blocking project gates
- Failure loop: stay in `he-implement` until every required Implement sub-stage and guardrail is resolved; return to `he-plan` only if owner or scope changed
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: ready for /he:verify: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and the next `/he:verify` command. Only `PASS` can say ready yes. No transcript dump
