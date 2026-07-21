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
5. For each `S-*` slice, specify mapped `R-*`/`F-*`/`C-*`/`T-*` IDs + changed owners + behavior + proof + demo + rollback + DoD.
6. Audit orphan requirements and horizontal-only groundwork; merge/delete or record approved reason.
7. Record exactly one `planned_paths` manifest per `S-ID` → run: `python3 "$HOME/.agents/skills/deterministic-checks/scripts/bounded_run.py" --timeout 600 -- python3 "$HOME/.agents/skills/he-build/scripts/audit.py" --admission --estimate-plan --repo <repo> --plan <PLAN.md>` → require one streamed PASS per slice before acceptance + rerun after final synthesis before approval.
8. `planned_paths` = exact candidate changed-path set; Build binds `--unit <S-ID>` to active slice + ordered completed prefix and accumulates completed units staged until a separately authorized Git boundary.
9. Review shard ≠ product slice; estimate partitions exact `planned_paths` into bounded review shards and reports `reviewShardCount`; never re-cut an accepted outcome only to fit audit transport.
10. Single-path budget FAIL → change the root owner/file boundary when structurally justified; otherwise blocker + exact owner; limit/ignore/omit weakening = forbidden.
11. Structural/safety/tool defect or timeout → stop run + blocker + exact owner; timeout increase, same-input retry, or per-slice full scan = forbidden.
12. Record `slice_count` = exact approved slice total; IDs = contiguous `S-1..S-n`.

## Complete

- Every approved requirement/flow/contract/technical owner/test/rollout action maps to ≥1 slice.
- Every slice has bounded owner surface + executable proof + demo + completion criterion.
- Cross-slice dependencies + first build action = exact; no orphan requirement or speculative slice.
- Final accepted-plan preflight + streamed PASS/review-shard count per slice = recorded before approval; estimate never guarantees future candidate content or replaces candidate/final audit.
- PLAN state `slice_count` = slice inventory count; mismatch blocks approval.
- Skip proposal only when no implementation will occur.
