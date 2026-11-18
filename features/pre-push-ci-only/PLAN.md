# Let a project leave the full pre-push check to CI

Status: Complete

## Outcome + scope

An optional shipping key, `pre_push_checks: "ci"`, makes pre-push skip the full check and leave it to CI. Pre-push still refuses a direct base push, warns about SSH, scans the pushed commits for secrets and runs the mutation report. Under CI, `check` fails when a gate changed a tracked file. Non-goals: reading branch protection, any change to projects that do not set the key.

## Sources + coverage

Sources: N/A — the request is the maintainer's chat message; no document or other source.

## Repository context

Owners: `.hooks/shipping.py` (policy keys), `.hooks/ship_actions.py` (`pre_push`), `.hooks/ci_jobs.py` (`load_checked_policy`, workflow lookup), `.hooks/process_group.py` (`report_gate_edits`, `ci_edits`, `policy_at`), `.hooks/gitleaks_scan.py` (`commit_secret_scan`), `.hooks/gate_runner.py` (`check --commit-secrets`).
Same cause: N/A — new behavior, no earlier fix of this cause.
Single source: N/A — the key has one owner, `shipping.py`; its docs line is in `.agents/skills/he-ship/references/checks.md` only. `gate_budget` moved to `gate_times.py`, `plan_base` to `plans.py` and `biome_children` to `dependency_graph.py` because the 1000-line file limit left no room; each has one copy. On the join with develop, the workflow rules have one owner, `workflow_blocking.py`: the `pull_request` filter rule (`narrowing_filters` and `covers_every_branch`) and the skippable-job chain (`skippable_jobs`, `${{ !cancelled() }}`). The key's workflow judge calls them; its own copies are removed. Only the rules the generated-form compare lacks stay in `ci_jobs.py`: the called-workflow lookup, the paired step conditions, the allowed arguments and commented-out commands.

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
- [x] A push-only or filtered-push workflow, a job or step with `if`, and `check --quick` or `--related-tests` are refused → `tests/test_shipping_policy.py::test_a_workflow_that_does_not_run_the_whole_check_on_every_pull_request_is_refused`: ten rows (the first six from challenge round 1, four from round 2: `--commit-secrets`, `--plan-stage Draft`, a commented-out command, a `needs` job with `if`) and three rows of round 3 (a `branches` list with `'**'` and a `!main` entry, in round 6; inline comment, paired conditions joined by `&&` with and without spaces, a caller that needs a conditional job) failed before the change and pass after.
- [x] The installed Hard Eng workflows, with their docs-only step pair, still count → `tests/test_shipping_policy.py::test_the_hard_eng_workflows_with_a_docs_only_step_pair_run_the_whole_check`.
- [x] A job or step `if` of only `!cancelled()` or `always()`, and a `branches` filter that holds `'**'`, do not refuse the workflow → `tests/test_shipping_policy.py::test_a_condition_or_filter_that_skips_no_pull_request_does_not_refuse_the_workflow`: three rows failed before the change and pass after. Found by loading the installed projects' workflows.
- [x] A failed base lookup in CI leaves the check unchanged → `tests/test_push_check.py::test_a_failed_base_lookup_in_ci_leaves_the_check_unchanged`.
- [x] A filtered or conditional `pull_request` run is refused, naming the filter → `tests/test_shipping_policy.py::test_a_called_check_workflow_is_refused_when_the_caller_filters_or_conditions_the_run` and `::test_a_check_workflow_with_a_filtered_pull_request_trigger_is_refused`: seven rows failed before the change and pass after.
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
Reader: a subagent that did not write the paragraph in `.agents/skills/he-ship/references/checks.md` quoted 5 sentences (the pre-push steps, "It takes effect", the long key sentence, "Under CI", the branch protection sentence); all were reworded into shorter sentences. After the round 3 prose a second Reader quoted 9 sentences (terse SSH and base push wording, the mutation step, who refuses, `needs`, the `if` exception, the argument list, the CI edit rule); each was reworded in the same commit. A third Reader (after the `'**'` and condition sentences) quoted 8; all eight were reworded or moved: mutation applies with `"ci"`, allowed versus refused wording, the `workflow_call` trigger wording, the formatter example, the two-needs sentence now lists both needs and says it fails with an error, the exception sentence names its scope and X, and the release sentence names the key.
Shards (rule added after a coordinator finding): `--shard rest` alone counts as the whole check only when no gate has `shards`; with a sharded gate the always-running jobs need `--shard rest` and `--shard merge`. Numbered shards need no judge rule, because `--shard merge` fails when any shard 1 to N sent no report (`merge_reports`, count read from the gate; tested in `tests/test_shards.py`). Red rows: rest only, numbered only, rest and numbered with no merge, merge only, shard job with a condition and a plain merge; each failed on the revision before the fix. Hard Eng's own six-shard workflow stays accepted, which needed the judge to allow a closed shell block before the check that only prints or exits non-zero.
Shard failure: a shard hidden with `|| true` or `continue-on-error` still writes a report with the failed test, and the merge fails on it, because the merged test report goes through the same report check as a single run. `tests/test_shards.py::test_the_gate_job_refuses_a_shard_report_with_a_failed_test` pins this for `failure` and `error`; it passed on the revision before this change, so the cause is already fixed and the judge needs no rule for numbered shard steps.
Review declined: the merge job can pass after the rest job fails because the judge does not require the merge job to need the rest job :: the rest job is its own red check on the pull request and CI stays required before merge; which checks gate a merge is branch protection, which the refusal text says cannot be read offline.
Review declined: shard detection reads package gates only, not shared gates :: `--shard` splits package groups only (`shard_groups` reads the package groups), so a `shards` key on a shared gate changes nothing and `--shard rest` still runs that gate.
Review declined: a block before the check refuses `;`, `&` or `|` inside quoted text of an `echo` line :: the refusal is the safe side, the message names the rule, and the fix is to write the printed text without those marks; quote-aware parsing of shell would add a parser for a rare line.
Journey A: a real installed project, plain `python3` hook through husky, key on in the base, one commit that changes one Dart file. It exited 0 after 460 s. The commit secret scan ran first (1.8 s). No full check ran. The quick gates ran (lockfiles 0.1 s and 6.0 s, codegen 121 s, format 4.1 s, file secret scan 21.9 s, changed-file analysis 163 s). Mutation stopped at its 120 s limit. Plain `python3` has no `yaml`; the hook process never imports it, and `check` re-runs itself through uv with pyyaml, so the workflow reader ran with no import error. Six setup steps were needed (gates `sources` lists, two Draft plans removed, newer skills copied, a lockfile regenerated, one line formatted). They came from the clone source, a local main branch 779 commits behind origin/main, which already ran the release this hotfix is based on; they are not a hotfix fault.
Journey B: the same project with an old main without the key and a pushed commit that adds the key. The full check path started (no left-to-CI line, no `--commit-secrets`) and stopped at plan validation after 12 s because the project had no plan for the change; no gate ran.
Failed lookups: `tests/test_push_check.py::test_a_failed_base_lookup_in_ci_leaves_the_check_unchanged` covers no base, no gates file, an invalid gates file, no shipping block and an absent commit; none raises or changes the result.
Installed projects: 16 installed projects load; 14 workflows accepted; 2 refused, each for a stated reason (a pull_request branch filter that skips PRs into other branches; a check run through a project wrapper script the text judge cannot read). Two faults of the judge found this way (`!cancelled()` and a `branches` filter with `**`) are fixed with red tests above. Limit: the workflow judge reads text and was not compared with real GitHub runs.
CI: hosted CI caught one failure the local run could not: with `CI` set, the CI guard read the base policy in the quick Stop check and started one more git process (`tests/test_gate_speed.py::test_stop_after_a_source_edit_starts_few_git_processes`, 32 against 31, reproduced with `CI=true`). The guard now skips the quick check.
Review declined: the CI edits guard skips a `--quick` check :: `--quick` is the local Stop check and no installed workflow runs it in CI; the guard's reason is the full gate that CI runs instead of pre-push, and the extra git process in the quick check failed a speed test under `CI=true`. The docs sentence says `without --quick`; no Reader check is needed for those two words.
Hardening (landed on develop): `tests/test_shipping_policy.py::test_a_workflow_that_does_not_run_the_whole_check_on_every_pull_request_is_refused` has rows for `|| true`, a pipe, a semicolon, `&&` then `||`, `&&` then a later line, `continue-on-error` on the step and the job, an `echo` of the command, and a conditional shell form on one line and on several lines; each failed before the change. `::test_a_condition_or_filter_that_skips_no_pull_request_does_not_refuse_the_workflow` has rows for `&&` then a command, a later line and the generated launcher line, which a real installed workflow holds.
Reader (hardening): a Reader quoted two sentences (shell `if` against the `if:` key, `&&` against `&`, `continue-on-error` with a false value); the sentences were split and name the shell form, `&&` and `true`.
Retro: (1) Escaped bug: none found on the base branch. (2) The 1000-line file limit forced two moves (`gate_budget`, `plan_base`) → None — the gate named the files.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to main.
