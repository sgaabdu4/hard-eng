# Send update failures and stale-scaffold notices to the agent

Status: Ready

## Outcome + scope

When a Hard Eng update fails, or a newer verified revision is waiting and no update is running, the agent is told to act: repair the cause as its own commit, then rerun setup, before other repository work. Until now these notices reached only the user in sessions that changed nothing, and the failure text told the agent to continue.

- A failed update result says to repair its cause as its own commit before other repository work, and to report a cause outside the repository to the user.
- The Stop hook of a session that changed nothing blocks once per turn when a newer verified revision exists and no update is running. Its reason carries the last update result. A running update or unverifiable freshness still only notifies the user.
- The failed-verification Stop reason follows the repair rule in `AGENTS.md`: every reported finding is repaired as its own commit, including findings unrelated to the task.

Non-goals:
- Naming failing project gates in update results: since #220 the update no longer runs the project's gates, so an update no longer fails on them.
- Notifying a running session the moment a background update finishes: the next Stop or session start reports it.

## Repository context

Owners:
- `.hooks/update_runner.py`: `failed_update` writes the failure text that session start reports; `stale_message` (now `stale_error`) builds the freshness notice used by `update.require_current`.
- `.hooks/agent_hooks.py`: `completion` and `unchanged_notice` build the Stop result. Only `decision: block` with `reason` reaches the agent; `systemMessage` is shown to the user.
- Observed: an installed project's update failed for hours. Every Stop showed the user "Use the supported updater", the agent never received it, and session start told the agent to continue with the existing scaffold.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for these fixes in one PR after asking why an agent carried on without repairing a failed update. The user asked for a GPT-6 Astra adversarial review loop before the PR, fixing only substantial, realistic findings. This reverses the earlier rule that staleness only warns in an unchanged session. The user wants the agent to repair before carrying on.

## Acceptance + steps

- [x] An unchanged session with a newer revision and no running update blocks, and its reason includes the last update result; an unchanged session whose freshness cannot be verified does not block → `test_completion_checks_freshness_without_mutating_installation`.
- [x] A running update stays a plain notice, and only a missing update is an `UpdateNeeded` → `test_stop_waits_for_running_update_instead_of_rerunning_setup`.
- [ ] Full check passes on the branch.

## Baseline + execution

Result: Passed
Evidence: main `f025ce02` passed the Hard Eng workflow on push (run 36668651585).
Execution: One builder on branch `update-failures-reach-agent`; GPT-6 Astra adversarial review before the PR.

## Risks + recovery

A stale scaffold that the agent cannot update, for example a network failure, adds one continuation per turn. The agent reports the cause and stops, and `stop_hook_active` prevents a loop. Recovery is reverting the change.

## ux_reference

N/A — hook messages only; no product appearance.

## Verification

Result: Pending
Evidence: Pending — full check on the branch.
E2E: N/A — the Stop hook is exercised through `completion` against a real Git repository; installed projects take the change with their next update.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
