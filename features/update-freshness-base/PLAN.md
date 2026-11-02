# Follow-up pushes on an update branch keep the freshness skip

Status: Complete

## Outcome + scope

A fix pushed onto an open Hard Eng update PR skips the freshness check in pre-push, as the PR's CI run already does. Before, pre-push compared the push with the remote branch tip, saw no update in that small diff, and ran freshness, which blocks on unrelated outdated dependencies. Non-goals: the freshness check itself, task branches without an update, and the package narrowing that also reads the push base.

## Repository context

Owners: `without_freshness_for_update` in `.hooks/gate_config.py` asks `installed_update_paths(root, base)` whether the diff from `base` is a verified update. `push_base` in `.hooks/ship_actions.py` passes the remote branch tip as `base` when the branch already exists, so a follow-up commit's diff holds no update. CI passes the PR base, so the same branch skips freshness there.
Cause (seen twice on 2026-11-02 in projects installed from this repository): an update PR needed a follow-up fix (a CI contract pin, a test fixture). Pushing it ran freshness locally and failed on dependencies the update did not touch, while CI for the same branch skipped it. One PR had to be closed and rebuilt from the default branch to get past it.
Same cause: `change_size.py` already judges the update from `default_branch_point`; no other caller of the push base decides a skip.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the user asked on 2026-10-31 for every Hard Eng update to land in each project and for Hard Eng gaps found on the way to be fixed here, failing test first.
Decided: keep the push-base check and add a second check from `default_branch_point`. CI behavior does not change, and the local result now matches it. A branch with no verified update still runs freshness.

## Acceptance + steps

- [x] A follow-up commit on a verified update branch skips freshness → `tests/test_updates.py::test_follow_up_push_on_update_branch_skips_freshness_like_ci[verified-update-False]`.
- [x] An unverified update still runs freshness → `tests/test_updates.py::test_follow_up_push_on_update_branch_skips_freshness_like_ci[unverified-update-True]`.
- [x] A branch without an update still runs freshness → `tests/test_updates.py::test_follow_up_push_on_update_branch_skips_freshness_like_ci[no-update-True]`.

## Baseline + execution

Result: Passed
Evidence: on `develop` 1252bc8 the new test failed only in the verified case (`['freshness', 'tests'] == ['tests']`); the other 5 selected tests passed.
Execution: One builder, this session. Failing test first, then the second check in `without_freshness_for_update`.

## Risks + recovery

The extra check runs only when the push-base check finds no update and the default branch point differs from the push base, so CI and first pushes do the same work as before. Revert the commit to restore the old local behavior.

## ux_reference

N/A — hook behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_updates.py` freshness, follow-up, scaffold-exemption and mixed-feature tests: 15 passed after the fix. The pre-push gate runs the full suite on this commit.
E2E: N/A — the rollout that hit the gap ran before this fix; the unit test replays its exact branch shape.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
