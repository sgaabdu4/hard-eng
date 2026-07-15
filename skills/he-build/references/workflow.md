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
9. Boundary learning trigger → `$he-learn` records/promotes candidate; prevention mutation stays in this loop.
10. No accepted finding → demonstrate slice → append exactly one `completed_slices` ID → next slice; all `slice_count` complete → `active_slice=final`.

## Final Convergence

Axes = intent/spec + deterministic + tests + review + security + UI/design + E2E/runtime + docs/context + unknowns.

1. Inventory applicability → checkpoint ordered `build_axes`; each axis = `pass | fail | na`; `na` requires proof; readiness = validator-derived.
2. Run full project gates + `$code-review`; route security/UI/performance/stack evidence only when applicable.
3. User-visible behavior → `$e2e` complete planned journeys:
   - existing UI = comparable before/after screenshots;
   - final states = required viewport/device screenshots;
   - primary temporal journey = video;
   - console/network + durable backend/state = verified.
   - requested/produced media = actual artifact review + canonical `$e2e` receipt PASS; runner/manifest PASS is insufficient.
4. Update PRODUCT/DESIGN/API/user docs only when accepted truth changed; run parity gates.
5. Any accepted finding/failure → PLAN issue → root fix → affected proof → repeat Final Convergence.
6. Prior axes PASS/N/A + `review=pending` → checkpoint → one complete bounded exact-evidence packet + rules/context + secret gate → zero-tool `scripts/audit.py` child + read-only profile denying source/controller homes.
7. Packet overflow → exact fail-closed owner; no truncation/partition/omission.
8. Timeout + zero review item = one infrastructure retry; second stall/finding/unknown = no retry + fail closed.
9. Parent consumes heartbeat + `he.audit.status` JSONL: `audit-starting → audit-retrying? → packet-review → transport-recovering? → synthesizing → completed|blocked|timed-out`.
10. Required finding → `finding_issue()` → PLAN issue provenance `audit + snapshot + axis + severity + source`; closure requires `disposition + proof + pass@new-snapshot`.
11. Child question → `unknowns` + concerns; parent records/asks/answers → new snapshot round. Interactive child wait = forbidden.
12. Auditor finding → verify claim → accepted = fix loop; rejected = record evidence.
13. Auditor clean + snapshot unchanged → readiness = `PASS/applicable × 100 = 100` + evidence current.
14. Open learning candidate → promote + prove in final loop; zero open candidate → `green`.

## Pause

- Missing intent/authority/external dependency → blocker/unknown + owner + next proof + `waiting_for`.
- Same root cause/failed approach ≥2 → `$repeated-failure-learning`; no blind retry.
- Before pause/turn end → atomic checkpoint + fresh inspect + exact resume action.
