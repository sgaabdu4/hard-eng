# Ship Workflow

## Enter

1. `he` inspect → require approved PLAN + `lifecycle_status=green`.
2. Assert exact green artifact before any delivery mutation:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" assert-green --repo <repo> --plan <PLAN>`

3. Assertion FAIL → no delivery mutation → checkpoint `building` + `he-build` final loop.
4. Read delivery policy + resolve the target + hooks + automatic workflows + downstream writes.
5. Record exact target/remote/branch/path/commit/push/PR/merge + environment/resource/effect/exclusions.
6. Recoverable delivery continues; an unrequested irreversible destructive action → checkpoint + one scoped question.
7. `deterministic-checks` `publish` → PASS; capture HEAD + status + actual diff.
8. PLAN `critical_overlay` slice in this delivery = current `deterministic-checks` mutation receipt; missing/incomplete → checkpoint `building` + `he-build` final loop.
9. Resolve active release actors for target + environment + revision; nonterminal manual/CI actor → wait or exact cancellation approval.

## Sync ⇄ Build

1. Fetch/prove upstream + ahead/behind + protection policy.
2. Synchronize the selected target without a separate protected approval.
3. Content/conflict/generated artifact change → checkpoint stale green + `he-build` final loop.
4. Unchanged snapshot → continue.

## Deliver

1. Re-run exact status/diff check immediately before mutation.
2. Commit only reviewed green product artifact; root `features/<slug>/` = local lifecycle state + reference/proof media + receipts → exclude unless an exact file was explicitly accepted as a product asset; bypass flags = forbidden.
3. After commit hooks complete + before dry-run/push, assert delivered HEAD exactly matches green and no non-lifecycle tracked/untracked bytes remain:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" assert-green --delivered-head --repo <repo> --plan <PLAN>`

4. Assertion FAIL, including unrelated dirty product work → push forbidden → checkpoint `building` + `he-build` final loop.
5. `git push --dry-run` → push → verify remote SHA.
6. PR policy → create/update exact PR + verify base/head/body; direct policy → verify target ref.
7. Resolve required workflows/jobs/steps from repository policy + affected-full classifier; proven non-impacted jobs may skip.
8. Verify each required GitHub run with `deterministic-checks` `github_delivery.py`; workflow-level green alone = insufficient.
9. Wait for required CI/review/merge policy; record run IDs/URLs + results for the delivered commit.

## CI ⇄ Build

- Product/code/test/doc finding → `he-build` root fix + affected proof + full pre-ship gate → restart Ship.
- Decisive same-root infrastructure flake → one policy-allowed retry; recurrence = exact external blocker.
- New deterministic failure/root → new `diagnosing-bugs` + `he-build` loop, not retry-budget exhaustion or goal completion.
- Explicit terminal artifact goal remains open until verified artifact receipt or exact stop condition.
- Failure after external mutation → apply global Release recovery + inventory current deployed state + exact failed stage; alternate actor/retry waits for terminal receipt.
- External wait → checkpoint exact resume condition; monitoring follows explicit user request.

## Finish

1. Verify delivered ref/PR/merge + CI against delivery SHA; this SHA permanently identifies remote product bytes.
2. Delivered UI proof requested/produced → canonical `e2e` receipt validator PASS for delivered revision/environment.
3. Record verified process learning for `he-learn`; do not delay delivery unless protected-boundary risk remains.
4. Refresh PLAN token → local `he` checkpoint:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=shipped --set active_slice=none --set "completed_slices=<ordered-comma-list>" --set "next_action=<delivery-SHA + URL + result>"`
5. Terminal checkpoint registers only that slug's PLAN + receipts in the repository-common local Git exclude; linked worktrees share the status cleanup while tracked files + other feature assets remain visible.
6. Post-delivery checkpoint bytes = local lifecycle state, not delivered product artifact; do not amend/create/push another commit unless repository policy requires that metadata delivery.
