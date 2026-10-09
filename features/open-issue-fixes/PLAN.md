# Fix open issues 265, 266 and 267, and the eval grader pass pattern

Status: Complete

## Outcome + scope

1. The turn-end check waits while background agents still edit the session's files (#265).
2. `update-pr` pushes a new update branch after GitHub deleted the old one (#266).
3. Agents give direct test, build and check runs a time limit (#267).
4. The agent eval grader counts a gate pass line that includes its elapsed time.

Non-goals: a `run --limit` wrapper, Codex background detection (Codex sends no background task list).

## Repository context

Owners: `.hooks/agent_hooks.py` `completion`; `.hooks/update_pr.py` `replaceable_remote`; `.agents/skills/he-build/SKILL.md`; `tests/agent_checks.py` `PASSED`. Claude's Stop hook input lists in-flight `background_tasks` with types such as `subagent`, `workflow` and `teammate` (https://code.claude.com/docs/en/hooks).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked to fix the open Hard Eng issues in this PR. Shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] A failing check does not block a turn while a subagent, workflow or teammate runs; a running shell task still blocks; no check runs → `test_turn_end_waits_for_running_background_agents_before_checking` failed before the fix with `decision: block`, passes after.
- [x] A deleted remote update branch is recreated → `test_update_pr_recreates_the_update_branch_after_the_remote_deleted_it` failed before the fix with `! [rejected] (stale info)`, passes after.
- [x] Direct runs get a time limit → `he-build` rule; `perl -e 'alarm shift; exec @ARGV' 2 sleep 5` stopped after 2 s with exit 142 on macOS.
- [x] The grader counts `PASS tests (exit 0; elapsed …)` → new planning-only case failed before the fix, passes after.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Branch commit `c284765b` passed `check --plan-stage Ready`: 18 gates, 1468 tests.
Execution: Single builder in a separate worktree while model evals ran from the main checkout.

## Risks + recovery

A session could end while agents still run, with no check. Recovery: the agents' completion wakes the session, and that turn end runs the check; the message says not to claim done.

## ux_reference

N/A — hook, updater and guidance changes with no visual surface.

## Verification

Result: Passed
Evidence: `pytest tests/test_update_pr.py` → 25 passed; `tests/test_stop_checks.py tests/test_agent_hooks.py` → 93 passed; `tests/test_agent_checks.py` → 28 passed. Full gate below.
E2E: N/A — each fix is proven at its real entry point: the Stop hook `completion` payload, `update_pr.publish` against a real Git remote, and the grader on recorded command output.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
