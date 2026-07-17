# Build Workflow

## Enter + Resume

1. `$he` inspect → emitted `recovery_action` completes + fresh inspect → require `build-ready|building` + `$he-build` route before mutation/proof.
2. `$deterministic-checks` worktree `write` → PASS; required handoff → complete `$he` Transfer → destination PASS.
3. Read approved outcome + flows + contracts + slices + proof + current items/evidence.
4. Compute exact non-PLAN snapshot → changed snapshot marks prior build evidence stale; PLAN checkpoint alone does not.
5. `build-ready` → checkpoint `building` + first incomplete active slice + current snapshot; `building` → require PLAN snapshot equals exact delivery HEAD + accumulated staged completed-slice artifact.
6. Author one unit against that exact state → export one canonical binary/full-index patch containing exactly active `planned_paths` → run `python3 skills/he-build/scripts/audit.py --admission --candidate-patch <patch> --unit <S-ID> --repo <repo> --plan <PLAN.md>` on Enter + Resume → require approval-receipt + active-path + scanner PASS before packet construction → require candidate PASS bound to unit/completed-prefix/accumulated-state/base/plan/patch/candidate IDs; accumulated bytes remain materialized dependency state, not repeated primary review; staged PLAN, stale PLAN snapshot, or unapproved dirt = FAIL.
7. Preserved composite WIP = every pending manifest path dirty + zero completed-path drift + extra path feature-local and verbatim-approved in PLAN → `candidateState=preserved-wip` + exact source snapshot + per-slice patch-byte match; audit clone mirrors bytes read-only; stash/reset/archive = forbidden.
8. With normal build mutation authority, run `python3 skills/he-build/scripts/apply_admitted_patch.py --repo <repo> --plan <PLAN.md> --patch <patch> --unit <S-ID> --expect-base <snapshot> --expect-patch <digest> --expect-candidate <snapshot>` → exact same-byte admission receipt cache hit requires identical tool + PLAN + base + patch + unit; otherwise rebuild admission → lock + clean state applies patch OR preserved WIP stages exact active bytes + verified exact index/file preimage rollback on detected post-mutation failure.
9. Plan-wide estimate = every slice evaluated against one shared index + every independent failure emitted in one run; fail-fast serial rediscovery = forbidden. Candidate/apply FAIL or delivery/PLAN/manifest drift → zero target mutation or verified rollback → preserve structured `code + marker/path` → false gate = fix global owner + regression; real project defect = fix active owner; unchanged intent = regenerate candidate automatically; changed scope/owner manifest = return to Slices; review shard count alone never re-cuts a product slice; `ROLLBACK_FAILED` = manual recovery; limit weakening/truncation/omission = forbidden.
10. Candidate/apply admission does not replace final audit; after each successful apply checkpoint the new exact snapshot before completing/advancing the slice; `building` → resume recorded next action.

## Slice Loop

1. Select one behavior from active slice → name precondition + action + observable result.
2. `$test-quality` TDD RED → fail for intended reason.
3. Implement minimum complete root-owner change + connected blast radius.
4. GREEN → focused new/affected proof PASS.
5. REFACTOR → remove duplication/wrappers/legacy; same proof PASS.
6. Run smallest applicable deterministic analyzers/scanners + specialist evidence; full project gates wait for Final Convergence unless active-slice risk requires them.
7. Gate finding → prove base/current attribution; introduced or behavior-connected = blocking; inherited unchanged = visible non-blocking per `$deterministic-checks`; touched file alone ≠ attribution. Normalize accepted findings → PLAN issue items; reject false/duplicate/taste-only claim with evidence.
8. Fix every authorized finding → recompute snapshot → rerun affected proof + review.
9. `remaining_work = incomplete slices + open required findings + failing gates`; each iteration closes ≥1 item OR adds material evidence; same root + count + proof twice → `$repeated-failure-learning`, not another retry.
10. UI-bearing slice → before UI mutation load root `DESIGN.md` + accepted UX/prototype → map every required actor × action × control × state × viewport to its production owner; missing material choice returns only affected UX decision; invention = forbidden. `$atomic-ui` + `$e2e` in accepted mock/local runtime before completion → compare implementation with accepted reference → exercise full map → inspect actual screenshots for hierarchy/density/spacing/a11y; mock proves UI/flow only, never persisted/deployment truth.
11. Boundary learning trigger → `$he-learn` records/promotes candidate; prevention mutation stays in this loop.
12. No accepted finding → demonstrate slice → invoke `$he` `complete-slice`; all `slice_count` complete → `active_slice=final`.

## Evidence Receipts

- Writer = `python3 "$HOME/.agents/skills/he-build/scripts/build_evidence.py" --repo <repo> --plan <PLAN> --axes <ordered-applicable-axes> --kind <full-matrix|specialist> --timeout <s> -- <argv>`.
- Full project matrix → `kind=full-matrix`; one command may bind every axis it proves.
- Focused proof = supplementary; never final evidence.
- Admission = approved plan digest + exact snapshot + artifact + current receipt per applicable pre-review axis; missing/stale/focused-only → fail before packet/reviewer tokens.

## Final Convergence

Axes = intent/spec + deterministic + tests + review + security + UI/design + E2E/runtime + docs/context + unknowns.

1. Inventory applicability → checkpoint ordered `build_axes`; each axis = `pass | fail | na`; `na` requires proof; readiness = validator-derived.
2. Run full project gates through Evidence Receipts + `$code-review`; independent read-only gates may run bounded-parallel; collect every same-snapshot failure before repair; route security/UI/performance/stack evidence only when applicable.
3. User-visible behavior → `$e2e` replay already-proven slice journeys + cross-slice transitions; first discovery of basic slice UI/layout/state = slice-proof process failure → fix + `$he-learn`. Complete planned journeys:
   - existing UI = comparable before/after screenshots;
   - final states = required viewport/device screenshots;
   - primary temporal journey = video;
   - console/network + durable backend/state = verified.
   - requested/produced media = actual artifact review + canonical `$e2e` receipt PASS; runner/manifest PASS is insufficient.
4. Update PRODUCT/DESIGN/API/user docs only when accepted truth changed; run parity gates.
5. Accepted failures → dedupe by cited `<owner-path>::<invariant>` → one connected fix bundle + every evidence citation retained; distinct root = distinct finding; recompute `remaining_work`; repeat only when it decreases or material evidence changes.
6. Evidence Receipts gate = PASS; deterministic axis requires `kind=full-matrix`.
7. Prior axes PASS/N/A + `review=pending` → checkpoint → bounded exact-evidence shards + rules/context + secret gate → one warm probe → completion-driven fan-out ≤8 from observed latency + deadline + selected `--latency-profile ordinary|urgent`; `cached_input_tokens` = telemetry only; child profile denies source/controller homes.
8. Coverage = every primary changed path assigned exactly once; dependency overflow → deterministic continuation shards + exact context coverage → aggregate capacity = shard count × strict per-shard limits before reviewer launch → aggregate validated shard findings/unknowns by semantic root losslessly into one verdict; indivisible primary evidence overflow = exact fail-closed owner; truncation/omission = forbidden.
9. Timeout + zero review item = one infrastructure retry; second stall/finding/unknown = no retry + fail closed.
10. Parent consumes heartbeat + `he.audit.status` JSONL: `audit-starting → shard-starting ⇄ audit-retrying? ⇄ packet-review|transport-recovering|synthesizing → shard-completed → completed|blocked|timed-out`.
11. Required finding → `finding_issue()` → PLAN issue provenance `audit + snapshot + axis + severity + source`; closure requires `disposition + proof + pass@new-snapshot`.
12. Child question → `unknowns` + concerns; parent records/asks/answers → new snapshot round. Interactive child wait = forbidden.
13. Auditor finding → verify claim → accepted = fix loop; rejected = record evidence.
14. Auditor clean + snapshot unchanged → readiness = `PASS/applicable × 100 = 100` + evidence current.
15. Audit receipt = aggregate usage + elapsed + shard count + prefix bytes + cache ratio + tokens + serial probes + workers + latency profile/target.
16. Open learning candidate → promote + prove in final loop; zero open candidate → `green`.

## Pause

- Missing intent/authority/external dependency → blocker/unknown + owner + next proof + `waiting_for`.
- Same root cause/failed approach ≥2 → `$repeated-failure-learning`; no blind retry.
- Before pause/turn end → atomic checkpoint + fresh inspect + exact resume action.
