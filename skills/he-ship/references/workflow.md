# Ship Workflow

## Enter

1. `$he` inspect → require `green|shipping` + `$he-ship` route + current evidence `100`.
2. Read target/remote/delivery/merge policy + exact authorized scope.
3. `$deterministic-checks` `publish` → PASS; capture branch + HEAD + status + diff + PLAN snapshot.
4. Missing policy/authority → PLAN blocker + `waiting_for`; existing exact authorization → continue.

## Sync ⇄ Build

1. Fetch target → prove upstream + ahead/behind + protection policy.
2. Rebase/synchronize only inside authorized scope.
3. Recompute artifact + evidence snapshot.
4. Snapshot changed/conflict/finding → checkpoint issue + `building` + `active_slice=final` + `build_round+1` + affected axes + stale evidence → `$he-build` same turn.
5. Unchanged green snapshot → checkpoint `shipping` + continue.

## Deliver

1. Re-run `publish` gate + exact diff/status review.
2. Commit exactly one built non-PLAN artifact commit from recorded HEAD; index PLAN paths = forbidden; bypass flags = forbidden.
3. Run `plan_state.py reconcile-head --repo <root> --plan <PLAN> --expect-token <token>`.
4. Reconciliation requires exact `artifact_id`; success normalizes post-commit `snapshot_id`; mismatch/uncommitted artifact → `$he-build`.
5. Persist PLAN separately only when repository policy tracks lifecycle state.
6. `git push --dry-run` → actual push → verify remote SHA.
7. PR policy → create/update one PR + verify base/head/body; direct policy → verify target ref.
8. Wait required CI/review/merge policy; record URLs + checks + SHAs.

## CI ⇄ Build

- Product/code/test/doc finding → PLAN issue + final build round → `$he-build` same turn → repeat ship from Sync.
- Infrastructure flake with decisive evidence → one policy-approved retry; recurrence → blocker, not blind retry.
- External wait → checkpoint `shipping` + exact resume action; polling/monitoring follows user request + harness capability.

## Finish

1. Verify delivered ref/PR/merge + required CI against reconciled artifact SHA.
2. Requested/produced visual proof → require canonical `$e2e` receipt validator PASS for delivered revision/environment.
3. Invoke `$he-learn` consolidation → new candidate may checkpoint at `green|shipping`; prevention mutation atomically returns `$he-build`; zero open candidate continues.
4. Checkpoint `shipped` + `stage_status=complete` + `waiting_for=none` + receipt evidence.
5. Persist terminal PLAN only when repository policy requires it; do not mutate delivered code.
