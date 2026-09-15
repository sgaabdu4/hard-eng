# Enforce explicit UX evidence and incomplete planning handoffs

Status: Complete

## Outcome + scope

Reject visual readiness based on an unlabeled image or a prose-only design-system description. Require the actual screen, before/proposed captures, native capture procedure and inspected comparison in the existing plan. Surface incomplete planning at Stop even when the plan remains Draft or no files changed this turn. Preserve legitimate user questions, nonvisual work, new-app concepts and bounded Stop recovery.

## Repository context

The current validator accepts any Markdown image after a Passed declaration, while Draft returns before readiness validation. The Stop hook emits no planning warning on a successful Draft check and skips unchanged sessions. Existing UX guidance ambiguously permits a production component instead of an existing app screen. Change these existing owners and their tests; no new runner, evidence database or dependency.

## Decisions + authorization

Blockers: None
The user authorized implementation, testing and PR/main delivery. Evidence declarations are enforceable structure, not proof that a dishonest description or screenshot is genuine. Capture and visual inspection remain required in the project-native runner/browser/device. Native checks must reject missing evidence and display truthful readiness, without interpreting arbitrary assistant phrasing or adding an LLM judge.

## Acceptance + steps

- [x] Existing-screen readiness requires explicit before/proposed images, actual surface, native capture procedure and visual inspection evidence.
- [x] A new app may explain the absent baseline; nonvisual work retains its specific inapplicability reason.
- [x] Draft Stop identifies incomplete evidence before expensive verification, preserves material questions and warns on unchanged sessions.
- [x] Unblocked incomplete planning requests one bounded continuation; retries and read-only work retain their scope and report blockers without automatic implementation.
- [x] Native tests cover missing evidence, genuine Draft questions, read-only/retry behavior and valid readiness; focused CLI/host proof and source checks pass.
- [x] Existing UX guidance requires the real screen tree and forbids explanatory panels as baseline/proposal substitutes.

## Baseline + execution

Result: Passed
Evidence: Starting source 213a3a58b60685088e8dea668be8432832d7755a is the verified merged tree of 9a8d298e7e5dfadb43e9e52c119fe690a939266c. Native pre-push passed 636 tests and all checks in 175.14 seconds; main CI passed in 134 seconds. Reuse that exact source baseline and run the plan-only Ready check before edits.

## Risks + recovery

A Draft may be a legitimate question or an unfinished autonomous plan. Distinguish it using the existing Blockers field; never grant authority through hook feedback. Local capture paths may be private or ephemeral, so do not claim arbitrary image links are authenticated by a structural plan check. Keep native capture and visual review evidence scoped to its audience.

## ux_reference

N/A — this changes CLI validation and hook feedback, with no application screen.

## Verification

Result: Passed
Evidence: The first reviewed revision passed 652 tests, four performance cases and all native pre-push checks in 138.62 seconds; PR CI passed in 142 seconds. Review then exposed a Stop-only stage override that could weaken source-change completion checks. That override is removed. The 125-case focused suite proves that planning-only questions (including unfinished templates and ignored captures) warn without claiming checks, while new source edits and unrelated parked questions retain the Complete-plan requirement. Lint and whitespace checks pass. The final revised commit must pass pre-push and hosted CI again within the unchanged 180-second budgets.
E2E: Passed — native CLI fixtures reject incomplete visual planning, allow a genuine question to stop and warn on unchanged sessions. A native Codex Luna max session with this candidate Stop command in a disposable read-only fixture corrected an initial premature readiness message to an explicit missing-Surface blocker without edits. The fixture used synthetic declarations and proves host/hook integration, not image authenticity or product acceptance.

Published-updater hook verification remains delivery follow-up. Full greenfield, brownfield and production application journeys are separate unfinished acceptance work; this source change does not claim them.

Delivery target: Merge
Delivery: Pending — reviewed PR, main CI and native delivered check are required; full consumer feature and production journeys remain separate acceptance work.
