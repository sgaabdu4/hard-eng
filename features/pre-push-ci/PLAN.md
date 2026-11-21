# Leave the full check to CI on push in this repository

Status: Complete

## Outcome + scope

A push to a branch whose base is `develop` runs only the commit secret scan; CI runs the full check, sharded on hosted machines. Non-goals: any change to the pre-push code, to CI, or to installed projects' defaults.

## Sources + coverage

Sources: N/A — the request is the user's chat message ("why can't all the others do it through ci", then "do it now"); no other source.

## Repository context

Owners: `hard-eng.gates.json` `shipping` (the setting); `.hooks/ci_jobs.py::load_checked_policy` (its two conditions); `.hooks/ship_actions.py::base_leaves_checks_to_ci` (it takes effect only when the remote base says `"ci"`).
Same cause: N/A — no earlier change of this setting here. Installed projects already use `"ci"` through the same code.
Single source: N/A — one key in the one config file; no copy.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked for it in chat on 2026-11-21 ("do it now").

## Acceptance + steps

- [x] The setting meets both conditions → `load_checked_policy` on this branch printed `policy ok`: the `secrets-history` gate is present, `scan_git_history` is on, and `.github/workflows/hard-eng.yml` runs `hard-eng.py check` on every pull request.
- [x] Pre-push under a base that says `"ci"` runs only the secret scan → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_runs_one_cheap_check_and_no_full_gate_when_mutation_is_off` (existing test of the code path this setting turns on).
- [x] A leaked secret is still refused → `tests/test_push_check.py::test_the_commit_secret_scan_blocks_a_leaked_secret_when_checks_are_left_to_ci`.

## Baseline + execution

Result: Passed
Evidence: develop 8c9b8b2a: the `Hard Eng` and `Canary` workflows passed on that push.
Execution: One builder, this session.

## Risks + recovery

A fault that only the full check finds now reaches CI before a person sees it, not the push. CI is a required check on every PR, so it still blocks the merge. Recovery: remove the `pre_push_checks` line.

## ux_reference

N/A — config only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run --no-project --with pyyaml python -I -c '...load_checked_policy(root, cfg)'` printed `policy ok`. The two tests above run in the full check on this push and in CI.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) The first push was refused because a `hard-eng.gates.json` change always needs a plan → None — the refusal named the step. (2) User correction: builders ran the full check by hand and again at the push → `features/pre-push-ci/PLAN.md` acceptance line 1; builders now push once and CI runs the full check.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop, then a later branch push prints that the full check is left to CI.
