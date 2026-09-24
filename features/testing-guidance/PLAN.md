# Clarify test outcomes, E2E proof, deletion and evidence guidance

Status: Complete

## Outcome + scope

Agents identify expected outcomes + failure modes before implementation, prove affected journeys with real E2E where applicable while retaining useful focused tests, justify test deletion beyond E2E overlap, report unavailable regression/E2E proof, and record repeatable evidence. `AGENTS.md` stays brief; detail lives in the existing testing reference. Non-goals: enforcement machinery, mandatory TDD, E2E-only rules, numeric targets, test deletion or production code changes.

## Repository context

Owners: `AGENTS.md` `Tests =` rule and `.agents/skills/he/references/testing.md`. Existing Regression row already requires red-on-defect/green-with-fix and a stated gap when red evidence is unavailable. Artifact handling stays with `.agents/skills/e2e/SKILL.md#visual-proof-and-completion`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User requested the guidance change, then asked to commit, open a PR and merge, and approved this plan file to satisfy the pre-push gate.

## Acceptance + steps

- [x] `AGENTS.md` `Tests =` adds outcomes-first, applicable E2E + retained focused tests, deletion justification and a link to the testing reference.
- [x] `testing.md` adds outcomes-first intro, E2E/focused-test clause, a Deletion row and Completion evidence/artifact bullets; existing guidance preserved.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Unchanged `2f9b4ec` main passes its merged CI; guidance-only edits touch no Python sources.
Execution: Single builder; edit the two existing owners only.

## Risks + recovery

Longer `Tests =` rule adds instruction weight to every session; trim wording if it crowds other rules.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 803 tests passed; gitleaks file scan → no leaks; new links resolve to `.agents/skills/he/references/testing.md` and the E2E `Visual proof and completion` heading.
E2E: N/A — guidance-only change; no runtime journey affected.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
