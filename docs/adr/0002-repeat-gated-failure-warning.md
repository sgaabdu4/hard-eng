# 0002 — Warn on a repeated tool error, not on every failure

Status: Accepted
Applies to: `.hooks/agent_hooks.py`, `.hooks/failures.py`

## Context

The Claude failure hook asked for HE Learn after every failed tool call. A replay of 138 local sessions found 1,061 such notes. About four in five came after a first failure, and agents opened HE Learn after only 14 of 128 repeats, with no clear drop in the error coming back.

## Decision

- The failure hook adds context only from the third sighting of one tool error in a session. The key is the tool, the subagent and the error text with numbers, hex runs and UUIDs masked.
- Interrupts, user or permission refusals, hook errors, timeouts and bare exit codes never count.
- It warns and never blocks a tool call. Counts live in the session's state file.

## Consequences

The same replay gave 20 warnings: about 13 real loops, 3 false alarms and 4 unclear. A loop whose error text changes each try is missed. Codex has no failure event, so it gets no warning.

## Evidence

User approval, 30 October 2026, after the replay. [Plan](../../features/repeat-tool-failure-warning/PLAN.md) records the tests and the model eval.
