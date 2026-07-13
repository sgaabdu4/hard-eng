# Build Workflow

## Enter + Resume

1. `$he` inspect → require fresh PLAN + `build-ready|building` + `$he-build` route.
2. `$deterministic-checks` worktree `write` → PASS; required handoff → complete `$he` Transfer → destination PASS.
3. Read approved outcome + flows + contracts + slices + proof + current items/evidence.
4. Compute exact non-PLAN snapshot → changed snapshot marks prior build evidence stale; PLAN checkpoint alone does not.
5. `build-ready` → checkpoint `building` + first incomplete slice; `building` → resume recorded next action.

## Slice Loop

1. Select one behavior from active slice → name precondition + action + observable result.
2. `$test-quality` TDD RED → fail for intended reason.
3. Implement minimum complete root-owner change + connected blast radius.
4. GREEN → focused new/affected proof PASS.
5. REFACTOR → remove duplication/wrappers/legacy; same proof PASS.
6. Run smallest applicable deterministic analyzers/scanners + specialist evidence.
7. Normalize accepted findings → PLAN issue items; reject false/duplicate/taste-only claim with evidence.
8. Fix every authorized finding → recompute snapshot → rerun affected proof + review.
9. No accepted finding → demonstrate slice → append exactly one `completed_slices` ID → next slice; all `slice_count` complete → `active_slice=final`.

## Final Convergence

Axes = intent/spec + deterministic + tests + review + security + UI/design + E2E/runtime + docs/context + unknowns.

1. Inventory applicability → checkpoint ordered `build_axes`; each axis = `pass | fail | na`; `na` requires proof; readiness = validator-derived.
2. Run full project gates + `$code-review`; route security/UI/performance/stack evidence only when applicable.
3. User-visible behavior → `$e2e` complete planned journeys:
   - existing UI = comparable before/after screenshots;
   - final states = required viewport/device screenshots;
   - primary temporal journey = video;
   - console/network + durable backend/state = verified.
4. Update PRODUCT/DESIGN/API/user docs only when accepted truth changed; run parity gates.
5. Any accepted finding/failure → PLAN issue → root fix → affected proof → repeat Final Convergence.
6. Prior axes PASS/N/A + `review=pending` → checkpoint → base/HEAD + committed/WIP/untracked packet + rules/context + secret gate → zero-tool `scripts/audit.py` + read-only profile denying source/controller homes.
7. Parent consumes `he.audit.status` JSONL: `starting → packet-review → synthesizing → completed|blocked|timed-out`.
8. Required finding → `finding_issue()` → PLAN issue provenance `audit + snapshot + axis + severity + source`; closure requires `disposition + proof + pass@new-snapshot`.
9. Child question → `unknowns` + concerns; parent records/asks/answers → new snapshot round. Interactive child wait = forbidden.
10. Auditor finding → verify claim → accepted = fix loop; rejected = record evidence.
11. Auditor clean + snapshot unchanged → readiness = `PASS/applicable × 100 = 100` + evidence current.

## Pause

- Missing intent/authority/external dependency → blocker/unknown + owner + next proof + `waiting_for`.
- Same root cause/failed approach ≥2 → `$repeated-failure-learning`; no blind retry.
- Before pause/turn end → atomic checkpoint + fresh inspect + exact resume action.
