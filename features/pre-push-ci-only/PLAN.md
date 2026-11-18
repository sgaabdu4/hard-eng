# Let a project leave the full pre-push check to CI

Status: Complete

## Outcome + scope

An optional shipping key, `pre_push_checks: "ci"`, makes pre-push skip the full check and leave it to CI. Pre-push still refuses a direct base push, warns about SSH, scans the pushed commits for secrets and runs the mutation report. Under CI, `check` fails when a gate changed a tracked file. Non-goals: reading branch protection, any change to projects that do not set the key.

## Sources + coverage

Sources: N/A — the request is the maintainer's chat message; no document or other source.

## Repository context

Owners: `.hooks/shipping.py` (policy keys), `.hooks/ship_actions.py` (`pre_push`), `.hooks/ci_jobs.py` (`load_checked_policy`, workflow lookup), `.hooks/process_group.py` (`report_gate_edits`, `ci_edits`, `policy_at`), `.hooks/gitleaks_scan.py` (`commit_secret_scan`), `.hooks/gate_runner.py` (`check --commit-secrets`).
Same cause: N/A — new behavior, no earlier fix of this cause.
Single source: N/A — the key has one owner, `shipping.py`; its docs line is in `.agents/skills/he-ship/references/checks.md` only. `gate_budget` moved to `gate_times.py`, `plan_base` to `plans.py` and `biome_children` to `dependency_graph.py` because the 1000-line file limit left no room; each has one copy.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the maintainer asked for the setting. A hotfix may carry a new change the maintainer asked for (AGENTS.override.md), so it ships as a hotfix branch.

## Acceptance + steps

- [x] A policy without the key runs the same push commands as before → `tests/test_push_check.py::test_a_policy_without_the_key_runs_the_same_commands_as_before`: one `check` call with the narrow options, and no `ls-remote` or `fetch`.
- [x] A base that says `"ci"` runs only the commit secret scan when mutation is off → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_runs_only_the_commit_secret_scan_when_mutation_is_off`: one `check --commit-secrets --base <base>` call and the left-to-CI line.
- [x] With mutation on, the scan, a quick check and the mutation report run, and no full check → `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_still_runs_the_secret_scan_and_the_mutation_report`.
- [x] Under CI, a gate that edits a tracked file fails `check` only when the base policy says `"ci"` → `tests/test_push_check.py::test_under_ci_a_gate_that_edits_a_tracked_file_fails_only_when_the_base_leaves_checks_to_ci`: it failed (exit 0 instead of 1) before the guard and passes after; the key off and a clean run pass.
- [x] A `workflow_call`-only workflow counts only when a `pull_request` workflow calls it → `tests/test_shipping_policy.py::test_a_workflow_with_only_workflow_call_counts_when_a_pull_request_workflow_calls_it`: called passes; never called and called by a push-only workflow are refused.
- [x] A pushed commit that turns the key on does not skip its own check → `tests/test_push_check.py::test_a_pushed_commit_that_turns_the_key_on_still_runs_the_full_check` and `::test_a_second_push_after_a_commit_that_turned_the_key_on_runs_the_full_check`: the full check runs.
- [x] A pushed policy that names a base the remote does not name keeps the full check → `tests/test_push_check.py::test_a_pushed_policy_naming_a_base_the_remote_does_not_name_runs_the_full_check`.
- [x] The key is refused without a workflow that runs the check, without the history secret gate, or with `scan_git_history` off → `tests/test_shipping_policy.py::test_ci_push_checks_need_a_check_workflow_and_a_history_scan`.
- [x] A bad value is refused and the default is `"local"` → `tests/test_shipping_policy.py::test_load_policy_rejects_malformed_values` and `::test_load_policy_defaults_the_push_checks_to_local_and_accepts_ci`.
- [x] A direct base push is still refused with the key on → `tests/test_push_check.py::test_a_direct_base_push_is_refused_before_any_snapshot[ci]`.
- [x] A secret in a pushed commit that a later commit removes still blocks the push, with real gitleaks and the checkout on another branch; a clean push passes → `tests/test_push_check.py::test_the_commit_secret_scan_blocks_a_leaked_secret_when_checks_are_left_to_ci`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-18, origin/main 876f3ba5: the `Hard Eng` workflow passed on the merge of the previous hotfix.
Execution: One builder, this session.

## Risks + recovery

An older release refuses the unknown key (`shipping policy has unknown or missing keys`), so a project must take the release before it adds the key. Recovery: remove the key; a revert restores today's behavior. Branch protection cannot be read offline, so CI being required before merge is not checked.

## ux_reference

N/A — no visible UI; hook output and policy only.

## Verification

Result: Passed
Evidence: `pytest tests/test_push_check.py tests/test_shipping_policy.py tests/test_ship_actions.py`: 114 passed. `pytest tests/test_skill_links.py`: 11 passed.
E2E: N/A — the secret test above runs the real pre-push path with real gitleaks and a real snapshot checkout; no user interface.
Real service: N/A — no outside service is called; gitleaks runs locally.
Retro: (1) Escaped bug: none found on the base branch. (2) The 1000-line file limit forced two moves (`gate_budget`, `plan_base`) → None — the gate named the files.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to main.
