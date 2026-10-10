# Prompt cache lifetime default and subagent reuse rule

Status: Complete

## Outcome + scope

Setup writes `promptCacheTtl` and `subagentPromptCacheTtl` as `"1h"` into a project's `.claude/settings.json` when those keys are missing, keeping any value the project set. `model-roles.md` tells Claude to message a finished subagent for same-task follow-up work and start a new one for unrelated work. Non-goals: Codex equivalents (per-role Codex models need a model choice from the user), the user's global settings, any change to `AGENTS.md`.

## Repository context

Owners: `setup.py` `configure_hooks` owns the Claude settings defaults; `.claude/rules/model-roles.md` is installed by the existing rules scaffold (`features/claude-rules/PLAN.md`). Both keys and the values `"5m"` and `"1h"` exist in the installed Claude Code 2.1.296 settings schema; subagents get 5 minutes unless `subagentPromptCacheTtl` is set (https://x.com/alexgetmancom/status/2108858155153117618, reply by an Anthropic engineer naming both keys).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User chose to ship the cache setting in the scaffold, add the keys the Anthropic engineer named, add one terse reuse line to the model rules, skip Codex for now, then open a PR and merge.

## Acceptance + steps

- [x] Fresh project settings gain both keys as `"1h"`; a project's own values are kept → `test_claude_settings_default_fable_advisor_plain_style_and_no_attribution`.
- [x] The rule says to message a finished subagent for same-task follow-up and use a new one for unrelated work → diff of `.claude/rules/model-roles.md`.
- [x] Rules still install byte-equal and update cleanly → `pytest tests/test_updates.py -k claude_rules`.

## Baseline + execution

Result: Passed
Evidence: main at `2af229d8` had a passed `Hard Eng` CI run before this change.
Execution: Single builder; the two `setdefault` lines with the test change, then the rule line.

## Risks + recovery

On API billing a 1-hour cache write costs more than a 5-minute one, and projects that install Hard Eng now get it. Recovery: the project sets either key to `"5m"` in `.claude/settings.local.json` or `.claude/settings.json`; setup keeps it.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `.venv/bin/python -m pytest tests/test_hook_setup.py -k default_fable_advisor` → 2 passed; `.venv/bin/python -m pytest tests/test_updates.py -k claude_rules` → 4 passed.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — settings defaults and static rule text copied by the existing scaffold; the install and update tests cover delivery.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
