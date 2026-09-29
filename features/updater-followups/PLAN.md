# Cheaper update checks, a shorter session hook, remembered refusals and swept temporary files

Status: Complete

## Outcome + scope

The freshness check asks GitHub for main's SHA and walks commits only when it moved. The session hook times out after 60 seconds, and setup replaces the installed 3600-second entry. A background update the new hooks refused is not retried until upstream moves, the checkout changes or 24 hours pass. Day-old Hard Eng temporary directories and leftover push worktrees are removed.

Non-goals:
- Stopping fsmonitor daemons explicitly: with git 2.55 on macOS, removing a worktree ended its daemon within a second.
- Branches that predate #218: they run their own updater until they take one update.
- Updating only the default branch's checkout: the user chose to keep per-branch updates, because completion and shipping require the latest verified revision on every branch.
- A time-based freshness cache: it would let completion pass on a stale revision.

## Repository context

Owners:
- `.hooks/update.py` `latest_verified`: fetched a 100-commit page on every check (1.6–2.2s measured).
- `.hooks/agent_hooks.py` and `setup.py` `configure_hooks`: gave the session hook the stop hook's 3600s timeout; the session hook's work took 0.13–0.39s in installed repositories.
- `.hooks/update_runner.py` `apply_update` and `remove_stale_candidates`: retried a refused update on every session start (about 40s and 26 MB each), and removed only update candidates.
- `ship_actions.pre_push`: `hard-eng-push-*` directories and their worktree records outlive a killed pre-push.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to do every follow-up from #220 in one PR rather than defer any, and chose per-branch updates.

## Acceptance + steps

- [x] An unchanged upstream costs one 40-byte request (a 304, or the same SHA) and no commit walk; a moved one walks commits → `test_freshness_walks_commits_only_after_upstream_moves`.
- [x] Setup replaces an installed 3600s session entry with the 60s one without a duplicate, for Claude and Codex → `test_setup_shortens_the_installed_session_hook_without_duplicate`.
- [x] A refused background update is not repeated with the same revision and checkout, is retried after 24 hours or a changed checkout, and a manual run always retries → `test_background_update_does_not_repeat_a_refusal_until_inputs_change`.
- [x] A network failure is not remembered → `test_background_update_retries_after_a_network_failure`.
- [x] Day-old Hard Eng temporary directories and push worktrees are removed; fresh ones and unrelated names stay → `test_update_sweeps_day_old_hard_eng_temporary_directories`.

## Baseline + execution

Result: Passed
Evidence: main `9d041fc7` passed the Hard Eng workflow on push (run 36637175748).
Execution: One builder on branch `updater-and-mutation-followups`, one commit per behaviour.

## Risks + recovery

Codex asks users to trust hooks again after the session entry changes. Recovery is reverting the commit.

## ux_reference

N/A — updater and hook behaviour; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (1155 tests, 89.71% line coverage). The freshness check took 0.76–0.84s against this repository, down from 1.6–2.2s.
E2E: N/A — the updater tests run real Git updates against fixture releases; installed repositories take the change with their next update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
