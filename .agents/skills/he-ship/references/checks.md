# Native shipping checks

Load for configuring or running HE Ship. The initial verifier supports GitHub PRs whose head and base belong to `origin`; fork PRs and other providers are unsupported. Missing `gh`, authentication or configuration is a blocker. The checks use real Git/`gh` responses and trusted project commands. Fixture responses are only test evidence, not hosted delivery proof.

## Project contract

Add `shipping` to the existing `hard-eng.gates.json` from observed repository requirements:

```json
{
  "shipping": {
    "base": "main",
    "checks": ["hard-eng"],
    "ui_paths": ["web/**"],
    "ci_seconds": 180,
    "pre_push_seconds": 180,
    "delivery": []
  }
}
```

Values above are an example, not universal defaults. Use the actual target, required check names, UI owners and measured budgets. An empty UI path list explicitly describes a nonvisual project. Missing/invalid policy cannot pass a ship check. Existing pre-push rejects direct updates to the configured base and still verifies the actual pushed commit; the elapsed budget is an additional requirement, not permission to omit checks.

For deployment, `delivery` contains existing project verifiers: `{"name":"production","command":["python3","scripts/verify_deployment.py"]}`. Reuse a native project command before adding a script. Each receives `HE_SHIP_REVISION` and `HE_SHIP_PR_URL`; it must inspect the actual deployed state and emit JSON `{"status":"passed","revision":"<observed source revision>"}`. Nonzero exit, missing/wrong revision or absent required commands fail. A script that echoes the expected environment variable proves nothing; validate an old-version failure and current-version success at the deployed boundary.

Keep one declaration in the existing plan's Verification section:

```text
Delivery target: Deploy
Delivery: Pending — production verification and cleanup remain required.
```

Allowed targets: `PR`, `Merge`, `Deploy`. Local build acceptance stays in the existing checklist; full remote requirements stay explicitly pending until proven. No new plan Status values or unchecked future-delivery checkbox that prevents the necessary pre-push Complete gate.

## UI evidence in the PR

For changes matching `ui_paths`, use distinct, inspected GitHub attachments:

```markdown
Before: ![Before](https://github.com/user-attachments/assets/actual-before-id)
After: ![After](https://github.com/user-attachments/assets/actual-after-id)
```

The verifier checks availability and image/video type, not whether the screenshots show the right behavior. E2E owns that inspection. Keep the actual baseline and final capture context in the PR; do not upload sensitive content or fabricate a missing baseline.

## Commands + proof boundaries

From the task checkout, with its actual PR URL and plan:

```sh
python3 .hooks/hard-eng.py ship --plan PLAN.md --pr https://github.com/owner/repo/pull/123 --stage ready
```

`ready` verifies current PR identity, branch/build evidence, required checks and applicable UI attachments. It is read-only. `merge` runs the same gate before a head-matched merge; select the repository's merge method and invoke it only with existing merge authorization. A queued or pending merge is unfinished.

`delivered` requires actual merge/remote proof and, for Deploy, the configured runtime verification. Before cleanup, retain evidence and make sure no other task uses the checkout. Deliberately remove only known generated build/test artifacts; unknown ignored files are retained. Run `cleanup` from the repository's persistent checkout with `--worktree` naming the completed linked worktree. Native guards must pass; a changed/dirty/locked/current checkout or active Git index lock is retained. Cleanup does not manufacture delivery proof. Use `python3 -B` for the cleanup invocation so Python does not create new bytecode artifacts.

Cleanup requires the captured origin URL to remain the fetch and sole push endpoint. Multiple or differing push URLs and initialized submodules are retained for a repository-owned cleanup procedure; the generic command never force-removes them. Dirty submodule checks override Git's ignore settings.

Record returned results at the same relative plan path in the persistent checkout, recovering the plan from the verified merged revision before removal if needed. Preserve unrelated edits there. Source changes invalidate affected build proof; external outages do not erase valid local checks. Remote branch protection remains project-owned; this implementation does not change server rules or claim to control unrelated clients.
