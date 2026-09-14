# Verify updater plans and linked worktrees

Status: Complete

## Outcome + scope

For non-scaffold candidate checks, use the configured shipping base when present; otherwise use origin's freshly advertised default-branch HEAD commit. Preserve the active task's committed Complete plan scope, application gates and atomic rollback. Do not select unrelated historical Complete plans or include uncommitted plan edits.

Linked-worktree verification must accept Git's own common hooks directory while rejecting arbitrary external hook paths. Move the existing path guard to the existing project_pre_push owner; preserve custom-hook content checks and avoid writing shared hooks during verification.

## Repository context

.hooks/update.py currently only supplies --base when shipping policy exists. Frontline's clean committed task031b7df6 has no shipping policy, so its candidate falls back to HEAD and excludes the committed plan. Reuse .hooks/ship_actions.py remote_base to resolve/fetch the exact remote commit and tests/test_updates.py's native scope fixture. No new helper, configuration or file.

## Decisions + authorization

Blockers: None

The user authorizes Hard Eng fixes, full checks, PR/main delivery and safe task-branch cleanup. The Frontline task requested this verified updater repair. One builder owns the fix. Installed e0b9 predates the prior base fix; the documented fresh verified-source updater invocation is required for recovery.

## Acceptance + steps

- [x] Candidate checks find the current committed plan with and without shipping configuration using fresh remote state despite stale tracking refs.
- [x] Application failures and unavailable remote bases reject; unrelated working changes remain untouched and candidate worktrees are removed.
- [x] Unrelated historical plans remain outside the task scope.
- [x] Native scaffold verification passes in a linked worktree without changing the common hook; arbitrary external hook paths still reject.

## Baseline + execution

Result: Passed
Evidence: Source03ec1b4303bc31b232628ccf46ea18df929f2bb1 passed 17 gates,470 regressions,4performance tests, PR70CI34821627768, mainCI34821877076 and native delivery. Source and submodule worktrees were clean. Pre-edit Ready gate passed /tmp/he-update-default-ready.log; both updater defects were investigated before production edits against this same baseline.

## Risks + recovery

origin HEAD is the remote's authoritative default branch when no shipping policy is configured. A missing remote/default ref fails closed. Existing shipping policy takes precedence. Consumer recovery must use the freshly verified updater implementation in a fresh process; manually copying installed hooks is not adoption.

## ux_reference

N/A — updater transaction and Git comparison behavior have no visual interface.

## Verification

Result: Passed
Evidence: Native regressions reproduced absent-base and linked-worktree failures (/tmp/he-update-default-red.log). All70 updater/Husky/agent-hook cases pass (/tmp/he-update-default-tests-final.log). Six scope cases additionally pass with configured shipping base deliberately different from remote HEAD (/tmp/he-update-default-scope.log). The application-failure fixture now reaches and asserts the actual failing application check rather than an unrelated missing-package rejection. Frontline's real committed plan independently validates against fresh origin HEAD563ed9e8746609d5ba11add983f0adf27e1467a8, without plan/installed-file edits. Its124-check baseline remains task-reported; full supported adoption follows delivery. Native lint/format pass; final Complete gate follows.

Delivery target: Merge
Final Complete gate passed all17 checks,473 regression tests and four performance tests (/tmp/he-update-default-complete.log). Ready for ship — local implementation and verification complete; delivery not performed.

Delivery: Pending — PR CI, exact main CI, native delivered and safe branch cleanup, followed by supported consumer update/pre-push proof.

Outstanding coordinated work: Frontline baseline main delivery and booking E2E; broader efficiency/complexity audit, including recurring Semgrep timeouts. StaffToDo delivered with main workflows passed but default live runtime smoke skipped.
