# Pre-push mutation cap

Status: Complete

## Outcome + scope

Pre-push mutation testing stops after a time limit, so a large change does not hold a push for hours after its checks pass. The limit is the optional `shipping.pre_push_mutation_seconds` setting: default 120 seconds, 0 skips mutation at pre-push. The full report stays available with `python3 .hooks/hard-eng.py mutation --base <ref>`. Non-goals: no change to the checks that can fail a push, to `pre_push_seconds`, or to the mutation adapters.

## Repository context

Owners: [.hooks/ship_actions.py](../../.hooks/ship_actions.py) (pre-push), [.hooks/shipping.py](../../.hooks/shipping.py) (policy), [.hooks/mutation.py](../../.hooks/mutation.py) (existing `--seconds` stop); tests in [tests/test_shipping_policy.py](../../tests/test_shipping_policy.py) and [tests/test_ship_actions.py](../../tests/test_ship_actions.py).
Evidence: issue #396. Pre-push called `mutation --base <base> --in-place` with no `--seconds`; on a medium change it ran for over 2 hours after about 20 minutes of gates.
Same cause: none found. The `mutation` command already had a `--seconds` stop; pre-push did not use it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid filed issue #396. Standing approval to push, open PRs, decide and merge green PRs.
Decisions: Cap, not removal, so pushes still report mutants on small changes. The key is optional so installed policies written before it keep loading. Default 120 s keeps a push fast. `shipping.py` reached the 1,000-line limit, so the gate-time helpers moved to their own `.hooks/gate_times.py` with no behavior change, and the policy tests moved to `tests/test_shipping_policy.py`.

## Acceptance + steps

- [x] Pre-push passes the policy's mutation limit to the mutation run → `tests/test_ship_actions.py::test_pre_push_keeps_the_passed_push_over_budget_or_after_mutation_fails`.
- [x] A zero limit skips pre-push mutation → `tests/test_ship_actions.py::test_pre_push_skips_mutation_when_its_budget_is_zero`.
- [x] The policy defaults the limit to 120 s and accepts 0 → `tests/test_shipping_policy.py::test_load_policy_defaults_and_accepts_the_mutation_budget`.
- [x] The policy rejects a negative or boolean limit → `tests/test_shipping_policy.py::test_load_policy_rejects_malformed_values`.

## Baseline + execution

Result: Passed
Evidence: develop ce4dbb4 passed the focused shipping and pre-push tests before the change.
Execution: One builder.

## Risks + recovery

A capped run reports fewer mutants on a large change; the stop message names the command for the full report. Revert this PR to restore the uncapped run.

## ux_reference

N/A — CLI hook with no visual surface.

## Verification

Result: Passed
Evidence: Local `hard-eng.py check`: every gate passed except 6 Dart and Swift tests that also fail on develop in this container (no Dart or Xcode tools); the `hard-eng` CI check is their proof.
E2E: N/A — the next push of a large change is the full proof.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` green.
