# Update Hard Eng without rerunning the project's gates in a candidate worktree

Status: Complete

## Outcome + scope

An installed update applies a CI-verified revision after checking only that the new hooks accept the project's gate configuration: seconds, no checkout and no dependency install. Pre-push and CI then run the project's gates on the update commit, and they select every gate group because Hard Eng's files or gate configuration changed. The stale-candidate cleanup also removes unlocked candidates left by updaters that predate the repository lock, once they are over six hours old. This fixes #219's per-update cost, its unnamed failures and its disk and daemon leaks.

Non-goals:
- A TTL or ETag on the version check: since #218 it makes one to three GitHub API calls in a detached background process.
- Remembering failed revisions: a failure now takes seconds and names the rejected configuration.
- Sweeping `hard-eng-push-*` and `hard-eng-gate-*` temporary directories: about 160 MB in the report, with no owner that proves a directory is unused.
- Updating only the default branch's checkout: completion and shipping require the latest verified revision, so task branches would be blocked as stale.
- A lower SessionStart timeout: the hook only starts a detached process now, the change needs a hook-entry migration, and it cannot reach installs that predate #218.
- Stopping fsmonitor daemons explicitly: with git 2.55 on macOS, removing a candidate worktree ended its daemon within a second, so removing abandoned candidates ends theirs.
- Branches that predate #218 keep running their old updater until they take one update.

## Repository context

Owners:
- `.hooks/update.py` `verify_candidate`: after `verified_revision` proved upstream CI, it added a locked worktree of HEAD, initialised submodules (600s limit), wrote the planned files and ran the project's whole `check` (3500s limit) for any change outside the scaffold file list. The issue reports 1.2–2.9 GB candidates, about five minutes per attempt, and a failure that named no gate.
- `check_scaffold_update`: CI's scaffold-only path built the same candidate to compile the hooks and validate the gate configuration.
- `.hooks/update_runner.py` `remove_stale_candidates`: removed only candidates locked with a `hard-eng-update <pid>` reason. Updaters before #218 created unlocked candidates, which therefore leaked (about 21 GB across two repositories in the report).
- `.hooks/gate_config.py` `changed_packages`: any change under `.hooks/` or to `hard-eng.gates.json` selects every gate group, so pre-push and CI fully check an update commit.
- `rebase_sessions` moves the session base past the update commit, so the Stop hook does not check it; pre-push and CI do.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix the open issues in this PR. #219 is the only open issue, and it proposes applying the update as a local commit that the project's own pre-push and CI gates verify.

## Acceptance + steps

- [x] An update whose new hooks reject the project's gate configuration applies nothing and names the rejection → `test_scaffold_update_validates_retained_files_scanner[True]`.
- [x] An update that changes project configuration commits without running application checks or adding a worktree → `test_project_configuration_update_commits_without_rerunning_application_checks`.
- [x] Cleanup removes an unlocked candidate over six hours old and locked candidates whose update exited, and keeps a fresh unlocked candidate and a live locked one → `test_update_removes_only_candidates_whose_update_ended`.
- [x] README describes the new update verification → review of the diff.

Retired tests: `test_candidate_uses_remote_task_plan_scope`, `test_candidate_ignores_base_changes_the_branch_lacks`, `test_candidate_initializes_consumer_submodule_and_cleans_up`, `test_candidate_provisions_yaml_without_host_site_packages` and `test_configuration_candidate_without_origin_uses_head` proved the candidate's base selection, submodule initialisation, dependency provisioning and cleanup. No candidate exists any more; the replacement proof is a single `worktree list` entry after an update, plus pre-push and CI selecting every group for such commits.

## Baseline + execution

Result: Passed
Evidence: branch `ci-reuse-pr-result` at `91ebd8ae` passed all 18 gates in its pre-push run before this change.
Execution: One builder on the same branch and PR as the CI reuse change, at the user's request.

## Risks + recovery

A gate configuration that parses but fails a gate now lands as a local update commit; the next pre-push names the failing gate and blocks the push until it is fixed. Recovery is reverting the update commit, or this change.

## ux_reference

N/A — updater behaviour; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` passed all 18 gates (1131 tests, 90.23% line coverage). The three acceptance tests failed against the previous `update.py` and `update_runner.py`. Codex adversarial review (gpt-6-astra) approved with no findings.
E2E: N/A — the updater tests run real Git updates against fixture releases; a live consumer update follows the merge.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge together with the CI reuse change.
