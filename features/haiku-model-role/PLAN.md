# Haiku subagent role and Claude project defaults

Status: Complete

## Outcome + scope

`model-roles.md` gives Haiku 5.5 a role: narrow lookup subagents (finding files or code, pulling one fact, summarizing logs or CI output, simple browser checks) run on `model: "haiku"`, and the Opus line keeps research that needs judgment. Setup also writes `advisorModel: "fable"` and blank commit, PR and session-link attribution into the project's `.claude/settings.json` when those keys are missing, keeping any value the project already set. Non-goals: other personal settings (theme, effort, output style, plugins), overriding project values, Codex equivalents.

## Repository context

Owners: `.claude/rules/model-roles.md`, installed into projects by the existing rules scaffold (`features/claude-rules/PLAN.md`); `setup.py` `configure_hooks` already owns the Claude settings file. Project settings override user settings and both keys may be set there (https://code.claude.com/docs/en/settings-reference). Anthropic positions Haiku 5.5 for high-volume, narrowly scoped work and subagent lookups, and keeps Sonnet and Opus for complex agentic coding (https://www.anthropic.com/claude-haiku-5-5).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User asked to add the Haiku role to `model-roles.md`, blank attribution, and a Fable advisor added only when missing; user chose the `fable` alias over the 1M-context ID knowing it overrides their global value in these projects; shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Rule names Haiku for narrow lookups, forbids it writing code or making judgment calls, and narrows the Opus research line → diff of `.claude/rules/model-roles.md`.
- [x] Fresh settings gain `advisorModel: "fable"` and blank attribution; a project's own `advisorModel` and `attribution` are kept → `test_claude_settings_default_fable_advisor_and_no_attribution`.
- [x] Rule tests and full gate pass → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `b35a2a7e` + this plan → exit 0; main's passed CI reused, secret scan PASS.
Execution: Single builder; rule edit, then the settings defaults in `configure_hooks` with one test.

## Risks + recovery

A lookup routed to Haiku may need judgment it lacks. Recovery: rerun that subagent on Opus. The project `fable` value overrides a user's own advisor choice in that project. Recovery: set `advisorModel` in `.claude/settings.local.json`.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_updates.py -k claude_rules` → 4 passed (install copies rules byte-equal, update refreshes a changed rule). `uv run pytest` over the hook, adoption, setup, agent hook, MCP and update suites → 304 passed. Removing the `advisorModel` default fails the fresh-settings case.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — static rule text copied by the existing scaffold; its install and update tests cover delivery.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
