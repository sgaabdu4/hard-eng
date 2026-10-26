# Installed repos compact earlier and keep long output out of the chat

Status: Complete

## Outcome + scope

Setup adds three Claude Code settings to each installed repo's `.claude/settings.json` as defaults, and keeps any value the project already sets: `autoCompactWindow` 500000, `bashOutputMaxChars` 10000 and `subagentPromptCacheTtl` "1h". Non-goals: Codex settings, user-level settings, changing values a project already chose.

## Repository context

Owner: `setup.py` already sets the Claude defaults `advisorModel`, `outputStyle` and `attribution` with `setdefault`; the three new keys use the same place. Test: `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution`. This repo's own `.claude/settings.json` gets the same three keys.
Same cause: one cause in every installed repo, since none sets these keys. Local session logs showed long sessions near the 1M default compact point (about 967K) re-read their full history on every step, long command output stayed in history, and helpers rebuilt their 5-minute prompt cache after waits of 5 to 60 minutes. Sources: Claude Code docs for model config, tools reference output limits and prompt caching.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid approved the three values on 2026-10-26 and asked to ship them to main and develop.

## Acceptance + steps

- [x] A repo with no Claude settings gets the three defaults → `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution[project0-expected0]` passed.
- [x] A repo that already sets the three keys keeps its values → `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution[project1-expected1]` passed.

## Baseline + execution

Result: Passed
Evidence: main f10f7dfa local `check` passed before the change.
Execution: One builder, this session.

## Risks + recovery

Earlier compaction keeps less of a long session word for word. A project sets its own `autoCompactWindow` to change it; setup never overwrites a project value.

## ux_reference

N/A — settings only; no visible UI.

## Verification

Result: Passed
Evidence: focused test 2 passed; local `check` passed with 1959 tests and 0 findings.
E2E: N/A — the Canary new-project jobs run setup on real runners.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on PR #411 to main and PR #412 to develop.
