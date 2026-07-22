# Consistency Stage

## Audit

| Trace | Reject |
|---|---|
| `PRODUCT.md` ↔ feature outcome/scope/terminology | product contradiction + duplicate stable truth |
| `DESIGN.md` ↔ prototype/tokens/theme/components/assets | visual contradiction + parallel editable owner |
| Requirement ↔ flow ↔ UX/system state ↔ contract ↔ owner ↔ slice ↔ test ↔ telemetry | orphan or conflicting edge |
| Permission/security/privacy/a11y ↔ enforcement + proof | UI-only or unstated enforcement |
| Error ↔ recovery + support/observe behavior | dead-end failure |
| Data ↔ purpose + SSOT + lifecycle + migration/rollback | purposeless/duplicate/irreversible unknown |
| Release ↔ owner + threshold + rollback + flag removal | ownerless operation |
| Decision ↔ evidence + approval + consequence | assumption/recommendation recorded as accepted |

- Also reject: scope/terminology/prototype-contract conflict, unapproved skip, non-demonstrable slice, missing cross-repo/generated-source impact, hidden compatibility risk.

## Route

1. Materialize one trace row per approved requirement across every column above.
2. Traverse forward to find missing downstream owner/proof; traverse backward to find speculative implementation/test/telemetry.
3. Compare terminology, permissions, states, fixtures, prototypes, contracts, and data semantics across owners.
4. Challenge assumptions presented as decisions, recommendations as approvals, and limitations as harmless.
5. Route each defect to earliest owning stage; reopen that stage + downstream dependents.
6. Materialize `## Traceability` + `## Failure Model` + applicable `## Guarantee Model` through [admission.md](admission.md); broad requirement/test/guarantee labels = orphaned edges.
7. Run risk-tier independent plan challenge; route each finding to earliest stage; repeat until clean.
8. Run `plan-admission` validator; structural failure returns to owning stage.

## Complete

- Re-read all accepted content + current repository evidence; material inconsistencies + unmodeled reachable failures = zero.
- Every documented limitation is non-material or promoted to blocker/issue/unknown.
- Root `PRODUCT.md` + `DESIGN.md` validate; canonical owners contain current accepted state only; split artifacts link without duplicated prose.
