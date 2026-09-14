# Enforce setup completion and delivery prerequisites

Status: Complete

## Outcome + scope

Prevent green checks from masking missing shipping configuration or a stale installed scaffold. Distinguish installation, local verification and remote delivery. Use existing owners and tests only.

## Repository context

Plan validation checks local completion; pre-push accepts absent shipping policy. The updater selects CI-verified revisions only at session start. Completion checks code without checking freshness.

## Decisions + authorization

Blockers: None

The user authorized this bounded repair, source delivery and consumer verification. One builder; no new dependency, file or persistent state. Preserve unrelated consumer edits. Public evidence uses synthetic fixtures only.

## Acceptance + steps

- [x] Complete delivery plans and pushes reject missing shipping policy; local-only planning remains supported.
- [x] Completion and shipping reject stale or unverifiable installed revisions without mutating files; current installations and source development remain supported.
- [x] Installer and handoff wording distinguish installed files, local checks and remote delivery.
- [x] Existing tests prove failing and passing paths; source gates and verified main delivery precede consumer adoption.

## Baseline + execution

Result: Passed
Evidence: Source9277ea9 passed17 gates,480 regressions,four performance tests, PR77 CI34838211269 and main CI34838415076 with native delivery. The previous local plan receipt is preserved outside the repository. Run Ready before implementation.

## Risks + recovery

Unavailable GitHub evidence blocks a freshness claim without modifying files. Hooks depend on client activation; final-report truth still needs review. No generic state machine or natural-language authorization parser.

## ux_reference

N/A — command and hook enforcement has no visual application surface.

## Verification

Result: Passed
Evidence: The added regressions exposed stale/offline completion acceptance and missing shipping enforcement before repair. The final Complete gate passed all17 gates,489 regressions and four performance tests. Native shell installation, isolated updates, Husky forwarding and committed-snapshot rejection remain verified; existing push fixtures now supply the mandatory shipping policy. The changed skill validates. Diff review confirms no new files, dependencies or stored state. Consumer adoption remains a separate delivery step.

Delivery target: Merge
Delivery: Pending — source PR, exact main CI, native delivery, owned-branch cleanup and consumer verification.
