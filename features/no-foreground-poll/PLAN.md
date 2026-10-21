# No foreground polling

Status: Complete

## Outcome + scope

Agents in every project with Hard Eng stop waiting on long jobs with foreground sleep loops. A Claude Code shell hook denies a main-session sleep loop or long sleep and tells the agent to run the job in the background and wait for the exit notice. HE Build says focused checks run only the touched tests, analyzer and lint. Non-goals: a Codex hook, machine settings, test queues and the dropped speed ideas.

## Repository context

A measured agent log study found that about half of shell time was foreground polling (sleep, until and hidden sleeps), and that many full suites ran at the same time. Hard Eng had no check for this, and `challenge.md` told agents to wait in calls under 9 minutes. Owners: `.hooks/polling.py` (new, stdlib only, because `hard-eng.py` imports take about 270 ms per call), `POLL_HOOK` in `.hooks/agent_hooks.py`, `configure_hooks` in `setup.py`, the registry entry, `AGENTS.md`, HE Build and `challenge.md`.
Same cause: one cause, agents block the turn to wait for a job that the host can watch for them.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 whether Hard Eng should change after the study, with every decision made by the agent. Decided: deny only `while`/`until` loops that sleep 1 s or more and single sleeps of 30 s or more, so bounded `for` retries and short settle waits pass; subagents (`agent_id` set) and `run_in_background` calls pass; Claude only, because Codex returns long commands early and has no exit notice.

## Acceptance + steps

- [x] A main-session sleep loop, long sleep or hidden sleep is denied → `tests/test_polling.py::test_foreground_sleep_wait_is_denied`.
- [x] Background jobs, subagents, short waits and bounded retries pass → `tests/test_polling.py::test_background_subagent_and_short_waits_pass`.
- [x] Setup registers the hook for Claude only → `tests/test_hook_setup.py::test_hook_registrations_invoke_shared_runner`.

## Baseline + execution

Result: Passed
Evidence: `develop` 2bf22ce passed its required `hard-eng` CI check.
Execution: One builder.

## Risks + recovery

A hook call adds about 40 ms to each Claude shell call. A false denial costs one retry with `run_in_background`. A missing script or a call outside the repository allows the command (`|| true`), so the hook never blocks all shell use. Revert the commit to remove the hook; installed projects then keep a harmless `PreToolUse` entry until removed.

## ux_reference

N/A — agent hook with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the tests run the real hook script on real hook payloads.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
