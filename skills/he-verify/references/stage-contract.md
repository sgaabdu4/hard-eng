# he-verify Stage Contract

- Update `he-state.json` before/after each proof step; record proof findings in `findings[]`; validate it before any ready-yes handoff
- Record every Verify sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before readying Ship
- Targeted tests first; use `test-quality` for assertion, fixture, or gap design
- Run every command in `guardrails[]`; missing or failing guardrails route back to `he-implement`
- Confirm `guardrailInventory.touchedStacks[]` is non-empty and `guardrailInventory.requiredGuardrails[]` covers regex scanners, Git hooks, lint/analyze/typecheck, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention as `required` with matching `guardrails[]` evidence or `not_applicable` with reason/evidence
- Do not start E2E or ready Ship while UI/component SSOT reuse is unresolved, disputed, or missing `ssot-owner-reuse` evidence; route back to `he-implement`
- Record repeated misses, review gaps, process gaps, or missing future guardrails as learning/process findings for `he-learn`; otherwise skip `learning-capture` with reason/evidence
- Run `node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .` before readying Ship; every detected supported project root must have the required test, lint/static-check, and format coverage
- Run `security-review` or `performance-rescue` when requested or when those risks were touched, then `thermo-nuclear-code-quality-review`, then `e2e` last
- User-visible changes need real UI artifacts
- Auto-fix loop: diagnose failures, return code changes to `he-implement`, update state, rerun affected proof only, repeat until clean or blocked
- Failure loop: no ship handoff until every required Verify sub-stage, proof command, review, artifact, and guardrail is clean or the blocker is explicit
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: ready for /he:ship: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and the next `/he:ship` command. Only `PASS` can say ready yes. No transcript dump
