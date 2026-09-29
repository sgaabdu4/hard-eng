# Check only the affected packages when a verified update shares a change with feature work

Status: Complete

## Outcome + scope

When a change holds a Hard Eng update and feature work, and the update part matches its CI-verified release, `check` runs only the packages the feature work affects. Otherwise it keeps checking every package.

Non-goals: narrowing CI's tool selection (`impact`), which keeps every group so it never installs less than `check` may need.

## Repository context

Owners:
- `.hooks/gate_config.py` `changed_packages`: any change under `.hooks/`, `.agents/` or to `AGENTS.md` selects every package, so each PR that carries an update rechecks the whole project.
- `.hooks/update.py` `check_scaffold_update`: already proves a scaffold-only change against the verified release; its proof is reused for the update part of a mixed change.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for every #220 follow-up in this PR, including this previously deferred narrowing.

## Acceptance + steps

- [x] A verified update plus a feature change selects only the feature's package → `test_update_mixed_with_feature_work_checks_only_affected_packages[feature]`.
- [x] A changed gate configuration, an unverified release, an edited hook or the `impact` step selects every package → the other cases of the same test.

## Baseline + execution

Result: Passed
Evidence: main `9d041fc7` passed the Hard Eng workflow on push (run 36637175748).
Execution: One builder on branch `updater-and-mutation-followups`.

## Risks + recovery

Proving the update part fetches the release, adding seconds to such checks; any failure of that proof falls back to checking every package. Recovery is reverting the commit.

## ux_reference

N/A — check selection; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (1157 tests, 89.68% line coverage); before this change `changed_packages` selected every package for the feature case.
E2E: N/A — the test builds real Git histories with a fixture release; installed repositories take the change with their next update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
