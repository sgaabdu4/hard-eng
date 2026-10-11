# Subagent scope rules

Status: Complete

## Outcome + scope

`model-roles.md` tells Claude to delegate only read-only, parallel or noisy work, keep edits in one thread, use Sonnet implementers only for independent parts with one writer at a time on shared files, and message a finished subagent only when the follow-up needs its gathered context. `subagents.md` tells Claude that each brief states goal, output shape and limits and asks for a short summary. Each change replaces or adds one line. Non-goals: test rules, `he-build`, `he-plan`, cache settings, Codex rules.

## Repository context

Owners: `.claude/rules/model-roles.md` and `.claude/rules/subagents.md`, installed by the existing rules scaffold (`features/claude-rules/PLAN.md`). Evidence: Anthropic's multi-agent research post and Claude Code subagent docs say most coding fits one thread and a resumed subagent keeps its history; a controlled Google study found multi-agent setups lose on step-by-step tasks; one video test (Opus alone against Opus with Sonnet builders) took 33 minutes and $7.86 against 73 minutes and about twice the cost.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User asked for research and the scaffold changes it supports, then approved the proposed edits with "ok".

## Acceptance + steps

- [x] The five rule edits are in the two files, replacing text where possible → diff of `.claude/rules/`.
- [x] Rules still install byte-equal and update cleanly → `pytest tests/test_updates.py -k claude_rules`.

## Baseline + execution

Result: Passed
Evidence: main at `8cbcc8ba` had a passed `Hard Eng` CI run before this change.
Execution: Single builder; five line edits.

## Risks + recovery

The video result is one run on one app. The rules say "delegate only" for edits, so a project that wants parallel writers must say so in the task. Recovery: revert the lines.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `.venv/bin/python -m pytest tests/test_updates.py -k claude_rules` → 4 passed.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — static rule text copied by the existing scaffold; the install and update tests cover delivery.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
