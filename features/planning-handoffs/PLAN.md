# Check planning handoffs

Status: Complete

## Outcome + scope

Separate prerequisite clarification from proposal approval; support grounded design-system mocks and compact plans. No new controller or machine-wide settings.

## Repository context

Owners: `.hooks/plans.py`, `setup.py`, HE Plan, existing hook/plan/setup tests.

## Decisions + authorization

Blockers: None

Autonomous implementation, Terra review and delivery to origin/main are authorized. Hook execution and semantic evidence quality remain host/human boundaries.

## Acceptance + steps

- [x] Explicit clarification can pause; incomplete approval handoffs block, including missing/invalid handoff declarations and mixed plans.
- [x] Design-system mocks pass the declared UX contract; proposal/context remain required and existing-screen baselines remain required.
- [x] Project-local disabled Codex hooks stop setup without overwriting settings; native enable/trust guidance stays accurate.
- [x] The existing plan template uses brief fields/checklists; guidance distinguishes questions from approval.
- [x] Negative/positive native fixtures and independent diff review cover the changed contracts.

## Baseline + execution

Result: Passed
Evidence: `uv run --no-project --with pyyaml python .hooks/hard-eng.py check --plan-stage Draft` passed all 17 gates and 719 tests on starting revision bb6ceda.

Terra: handoff/UX validator and installer in separate files. Coordinator: skills/plan, integration and delivery; Terra cross-review afterward.

## Risks + recovery

Older active Draft plans need an explicit handoff choice. Preserve genuine prerequisite questions; do not interpret a writable declaration as trusted approval or claim hooks prevent every bypass.

## ux_reference

N/A — CLI validation and planning guidance have no application screen.

## Verification

Result: Passed
Evidence: 739 tests passed. The first Complete run found excessive complexity in one native Stop test; simplified assertions retain all seven passing scenarios and pass Ruff. Terra reviewed the combined diff with no remaining blocker. Metadata and changed links pass; final integrated verification runs before shipping.
E2E: Passed — native Draft/Ready/Stop fixtures prove the baseline can run before approval, incomplete approval blocks and a declared mock passes Ready. Installer fixtures reject disabled hooks without writes. These prove CLI contracts, not native-host compliance or visual authenticity.

Delivery target: Merge
Delivery: Pending — reviewed PR, required CI, merge and verified main revision.
