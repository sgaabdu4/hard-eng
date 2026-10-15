# Stop hook starts from the last pushed commit

Status: Complete

## Outcome + scope

The Stop hook measures the session's change from the later of the session's starting commit and the last first-parent commit already on any remote branch (issue sgaabdu4/hard-eng#308). A task branch built on a shared integration branch no longer checks the other tasks' commits.
Non-goals: no new configuration for integration branches; no change to pre-push or CI scope.

## Repository context

Owner: [agent_hooks.py](../../.hooks/agent_hooks.py) `session_scope`, added for #306, used the branch point on the remote default branch, which sits below every commit on an integration branch.
Evidence: a session whose own change was one workflow file failed format and type gates on another task's files that were already on the integration branch.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the new Hard Eng issues. Codex adversarial review loop (gpt-6-astra) before the PR.
Decisions: Commits already on a remote passed the pushing machine's pre-push gate, so they are not this session's change. This covers integration branches, the default branch and the task's own pushed commits without a configured branch list. With no remote, or no pushed ancestor, the session's starting commit stays. The `local` option added to `default_branch_point` for #306 is removed, since nothing uses it now.

## Acceptance + steps

- [x] A task branch on a shared branch passes the shared branch's tip as the base → `test_a_branch_on_a_shared_branch_checks_only_its_own_commits`, red before.
- [x] Others' merged work is still skipped and session edits are still checked → `test_work_merged_by_others_after_the_session_started_is_not_checked`.
- [x] Without a remote, the session's own commits are still checked → `test_update_commit_is_not_counted_as_session_work`.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, focused tests, consumer run, full check, Codex loop, PR.

## Risks + recovery

A commit pushed from a machine without Hard Eng is not rechecked at Stop; pre-push and CI still check any push from this machine. Recovery is reverting this branch.

## ux_reference

N/A — hook scope only; no product appearance.

## Verification

Result: Passed
Evidence: The new test failed before the fix and passes after; 240 focused hook, plan and update tests pass; the full check passes.
E2E: Passed — a consumer project clone at its default branch, with a local shared branch holding another task's code commit and a task branch changing one workflow file: the real Stop hook ran `check --quick --base <shared branch tip>` and reported only the workflow file.

Delivery target: Merge
Delivery: Pending — PR CI, then merge.
