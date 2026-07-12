# Slices Stage

## Decide

- Slice unit = independently demonstrable user/operational outcome; horizontal-only groundwork requires approved reason.
- Slice 1 = smallest end-to-end walking skeleton through required layers.
- Per slice record: outcome + flows + UI/components + API/data/permissions + validation/errors + tests + telemetry + flag + migration/rollback + dependencies + demo + DoD.
- Order by dependency + risk reduction + demonstrability; expose parallel work only when ownership is independent.

## Route

1. Build requirement/flow/owner/proof dependency graph from approved stages.
2. Cut smallest end-to-end walking skeleton that proves one real outcome through required layers.
3. Cut remaining vertical outcomes; attach each cross-cutting migration/flag/telemetry task to its consuming slice.
4. Order by hard dependency → irreversible risk reduction → user-visible value; mark truly independent parallel owners.
5. For each slice, specify changed owners + behavior + proof + demo + rollback + DoD.
6. Audit orphan requirements and horizontal-only groundwork; merge/delete or record approved reason.

## Complete

- Every approved requirement/flow/contract/technical owner/test/rollout action maps to ≥1 slice.
- Every slice has bounded owner surface + executable proof + demo + completion criterion.
- Cross-slice dependencies + first build action = exact; no orphan requirement or speculative slice.
- Skip proposal only when no implementation will occur.
