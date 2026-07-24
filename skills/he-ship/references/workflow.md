# Ship Workflow

## Enter

1. `$he` inspect → require approved PLAN + `lifecycle_status=green`.
2. Assert exact green artifact before any delivery mutation:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" assert-green --repo <repo> --plan <PLAN>`

3. Assertion FAIL → no delivery mutation → checkpoint `building` + `$he-build` final loop.
4. Read delivery policy + exact approved target/remote/branch/path/commit/push/PR/merge scope.
5. Missing exact destructive/external/commit/push/merge/publish approval → checkpoint + one scoped question.
6. `$deterministic-checks` `publish` → PASS; capture HEAD + status + actual diff.

## Sync ⇄ Build

1. Fetch/prove upstream + ahead/behind + protection policy.
2. Synchronize only within exact authorization.
3. Content/conflict/generated artifact change → checkpoint stale green + `$he-build` final loop.
4. Unchanged snapshot → continue.

## Deliver

1. Re-run exact status/diff check immediately before mutation.
2. Commit only reviewed green product artifact; include pre-delivery PLAN bytes only when repository policy explicitly requires them + they were reviewed; bypass flags = forbidden.
3. After commit hooks complete + before dry-run/push, assert delivered HEAD exactly matches green and no non-lifecycle tracked/untracked bytes remain:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" assert-green --delivered-head --repo <repo> --plan <PLAN>`

4. Assertion FAIL, including unrelated dirty product work → push forbidden → checkpoint `building` + `$he-build` final loop.
5. `git push --dry-run` → actual authorized push → verify remote SHA.
6. PR policy → create/update exact PR + verify base/head/body; direct policy → verify target ref.
7. Wait for required CI/review/merge policy; record SHA + URL + results.

## CI ⇄ Build

- Product/code/test/doc finding → `$he-build` root fix + affected proof + full pre-ship gate → restart Ship.
- Decisive infrastructure flake → one policy-allowed retry; recurrence = external blocker.
- External wait → checkpoint exact resume condition; monitoring follows explicit user request.

## Finish

1. Verify delivered ref/PR/merge + CI against delivery SHA; this SHA permanently identifies remote product bytes.
2. Delivered UI proof requested/produced → canonical `$e2e` receipt validator PASS for delivered revision/environment.
3. Send verified process learning to `$he-learn` asynchronously; do not delay delivery unless protected-boundary risk remains.
4. Refresh PLAN token → local `$he` checkpoint:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=shipped --set active_slice=none --set "completed_slices=<ordered-comma-list>" --set "next_action=<delivery-SHA + URL + result>"`
5. Post-delivery checkpoint bytes = local lifecycle state, not delivered product artifact; do not amend/create/push another commit unless repository policy + exact approval separately require that metadata delivery.
