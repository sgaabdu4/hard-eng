# Make the update path finish and explain itself

Status: Complete

## Outcome + scope

Issues 253, 254 and 255. The CI scaffold check no longer fails when the runner's hooks folder sits outside the checkout, and the hooks error names the folder, the checkout and where `core.hooksPath` was set. `update` waits for its run, prints the recorded result and exits 1 on failure, and says so when another update holds the lock. A clean worktree that has `hard-eng/update` checked out is no longer called unfinished work: the update stops with that worktree's path and how to free it, and the fix steps say to remove the worktree once the fix merges. A setup refusal's reason reaches the recorded result and the failure file, and the update log is appended to instead of wiped. `update-pr --no-merge` pushes and opens the PR, then prints the merge command for the user. No new file other than this plan.

## Repository context

Owners: `.hooks/update.py` (`update_plan`, `release_installed`), `.hooks/update_runner.py` (`run_update`, `start_update`, `unfinished_update`, `build_update`), `.hooks/update_pr.py` (`publish`, `fix_steps`, `next_step`), `.hooks/agent_hooks.py` (`project_pre_push`), `.hooks/hard-eng.py` (CLI). Guidance: `AGENTS.md`, `.agents/skills/he-ship`, `README.md`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open issues in one PR and to run a GPT-6 Astra Codex adversarial review loop before the PR, acting only on genuine, realistic, substantial findings. Issue 255 takes its first suggestion (`--no-merge`). The CI scaffold check keeps comparing against the new release as both source and previous, as before.

## Acceptance + steps

- [x] The scaffold check passes with a hooks folder outside the checkout, and the hooks error names it → `test_linked_worktree_may_use_the_common_checkout_hooks`, `test_committed_scaffold_exemption_preserves_application_boundary`.
- [x] `update` prints its result, exits 1 on failure and reports a held lock → `test_update_prints_its_result_and_fails_when_the_update_failed`, `test_interrupted_update_stops_every_process_and_records_failure`.
- [x] A clean checked-out update branch is named with how to free it, and the update runs once it is freed → `test_background_update_names_a_clean_checked_out_update_branch`.
- [x] A setup refusal's reason is recorded and replayed → `test_background_update_records_why_setup_refused_it`.
- [x] `update-pr --no-merge` never requests a merge and prints the command → `test_update_pr_merges_only_after_every_check_on_the_pushed_head_passed`.
- [x] `update-pr --no-merge` prints the merge command only once checks pass → same test (Codex round 1).
- [x] A Husky launcher changed under the hooks override loses the scaffold exemption, and the common checkout's Husky hooks are still verified → `test_linked_worktree_may_use_the_common_checkout_hooks` (Codex round 1).
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 518c4a3. Each new or changed test failed on main's `.hooks` and passes on this branch.
Execution: Single session on `fix/update-path-issues`; two Codex adversarial review rounds on GPT-6 Astra.

## Risks + recovery

A worktree with uncommitted edits on the update branch still counts as unfinished work, so the update waits for it. In CI with a hooks folder outside the checkout, an update that changes `.husky/pre-push` runs the full checks instead of the scaffold shortcut. Left unfixed after Codex round 2 as unrealistic: a fix amended into the generated update commit, in a clean checked-out worktree, is treated like a plain update commit; fix steps say to add a commit, and main already treats an amended branch without a worktree the same way. Recovery is reverting this branch.

## ux_reference

N/A — command output and error text only; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a scratch Git project installed from this branch with a bare origin, `python3 .hooks/hard-eng.py update` printed its recorded result (a failure, since the branch revision is not on GitHub) and exited 1; with the repository's update lock held it printed that another update is running and exited 0.
Evidence: `hard-eng.py check --base origin/main --plan-stage Ready` exit 0: 18 checks passed, 1452 tests, 91.09% line coverage. Each new regression failed on main's `.hooks`.

Delivery target: Merge
Delivery: Pending
