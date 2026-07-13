# Plan Artifact

## Ownership

- Required repository owners = root `PRODUCT.md` + root `DESIGN.md`; structure/workflow owners = Stage Route product context + `$atomic-ui` DESIGN.md route.
- Default = one `PLAN.md`: router state + approved synthesis + traceability + slices.
- Split only when independently reviewed/generated or too large for clear ownership.

| Earned condition | Optional owner |
|---|---|
| Reusable research evidence | `CODEBASE_RESEARCH.md` |
| Independent product/flow/UX/contract/technical/test/rollout review | matching `FEATURE.md`, `FLOWS.md`, `UX.md`, `CONTRACTS.md`, `TECHNICAL.md`, `TESTING.md`, `ROLLOUT.md` |
| Generated API contract | `openapi.yaml` |
| Interactive visual proof | `prototype/` + selected assets |
| Long-lived independently reviewed decision | `DECISIONS.md` |

- `PLAN.md` links split owners; duplicated prose, empty templates, chat/rejected/migration history = forbidden.
- Raw reusable research → project convention; absent convention → `.research/`, uncommitted unless approved.
- Material decision record = ID + context + options + recommendation + verbatim user decision + evidence + consequences/risks + revisit trigger.

## Approval Inventory

- Root product/design paths + validity + evidence revision + approved delta/no-delta.
- Research baseline + declared limitations.
- Problem/outcomes/scope/non-goals/users/stakeholders.
- Flows + UX/prototype + reused/modified/new owners.
- Contracts/data/permissions + technical/security/privacy/a11y design.
- Testing + rollout/telemetry/owners + vertical slices/dependencies.
- Decisions + risks/mitigations + deferred work + approved skips + affected product/design/architecture/doc owners + DoD + exact first action.

## Route

1. Validate root `PRODUCT.md` + `DESIGN.md`; reject missing/invalid/drift/duplicate owner.
2. Read approved/skipped stage prefix + consistency result; reject any missing stage/open item.
3. Synthesize current accepted decisions into `PLAN.md`; link earned split owners instead of copying them.
4. Remove duplicate, stale, rejected, conversational, template-only, or migration-history content.
5. Walk Approval Inventory + full traceability; resolve gaps in earliest owning stage.
6. Present compact implementation view: outcome + owners + slices + proof + rollout + risks/limits + first action.
7. Present the canonical implementation view for the final user decision.

## Complete

- Root context pair = valid/current/approved; every earlier stage = approved/skipped; consistency approved; blockers/issues/unknowns = zero.
- Research complete for declared repositories/revisions/scope; material inaccessible area = blocker.
- User explicitly confirms `PLAN.md` fully represents intended implementation.
- `PLAN.md` contains one authoritative value per decision.
