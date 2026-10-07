# Haiku subagent role

Status: Complete

## Outcome + scope

`model-roles.md` gives Haiku 5.5 a role: narrow lookup subagents (finding files or code, pulling one fact, summarizing logs or CI output, simple browser checks) run on `model: "haiku"`, and the Opus line keeps research that needs judgment. Non-goals: changing the Opus, Sonnet or advisor roles, Codex equivalents.

## Repository context

Owners: `.claude/rules/model-roles.md`, installed into projects by the existing rules scaffold (`features/claude-rules/PLAN.md`). Anthropic positions Haiku 5.5 for high-volume, narrowly scoped work and subagent lookups, and keeps Sonnet and Opus for complex agentic coding (https://www.anthropic.com/claude-haiku-5-5).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User asked to add the Haiku role to `model-roles.md`; shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Rule names Haiku for narrow lookups, forbids it writing code or making judgment calls, and narrows the Opus research line → diff of `.claude/rules/model-roles.md`.
- [x] Rule tests and full gate pass → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `b35a2a7e` + this plan → exit 0; main's passed CI reused, secret scan PASS.
Execution: Single builder; one rule file edit.

## Risks + recovery

A lookup routed to Haiku may need judgment it lacks. Recovery: rerun that subagent on Opus.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_updates.py -k claude_rules` → 4 passed (install copies rules byte-equal, update refreshes a changed rule).
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — static rule text copied by the existing scaffold; its install and update tests cover delivery.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
