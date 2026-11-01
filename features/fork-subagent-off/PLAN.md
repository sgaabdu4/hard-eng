# Installed repos turn off the Claude Code fork subagent

Status: Complete

## Outcome + scope

Setup adds `env.CLAUDE_CODE_FORK_SUBAGENT` "0" to each installed repo's `.claude/settings.json` as a default. It keeps a value the project already sets and keeps other `env` keys. Non-goals: Codex settings, user-level settings, changing values a project already chose.

## Repository context

Owners: `setup.py` `configure_hooks` already sets the Claude defaults (`features/cost-settings/PLAN.md`); the new key uses the same place. `merge` rejects a changed value, so setup adds `env` only when the key is absent. Test: `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution`. This repo's own `.claude/settings.json` gets the same key.
Same cause: N/A — a new setting; no earlier fix. No file in this repo set the key before.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid asked on 2026-11-01 to set the value to "0" here and in every repo that uses the scaffold, and to merge to develop and main.

## Acceptance + steps

- [x] A repo with no Claude settings gets `env.CLAUDE_CODE_FORK_SUBAGENT` "0" → `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution[project0-expected0]` passes.
- [x] A repo that already sets the key keeps its value and other `env` keys → `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution[project1-expected1]` passes.
- [x] A repo with other `env` keys keeps them and gets the new key → `tests/test_hook_setup.py::test_claude_settings_default_fable_advisor_plain_style_and_no_attribution[project2-expected2]` passes.

## Baseline + execution

Result: Passed
Evidence: develop b4f5c6d: Hard Eng CI run 41262777417 passed; focused `tests/test_hook_setup.py` + `tests/test_setup.py` passed. A later local `check` failed `freshness` for a new types-pyyaml release, repaired first in PR #458. 6 Dart and Swift tests fail locally only because this container has no `dart` or `swiftc`; CI installs both.
Execution: One builder, this session.

## Risks + recovery

A project that wants the fork subagent sets the key to "1"; setup never overwrites a project value.

## ux_reference

N/A — settings only; no visible UI.

## Verification

Result: Passed
Evidence: focused `tests/test_hook_setup.py` + `tests/test_setup.py` 77 passed; the 3 cases fail without the `setup.py` change; pyrefly 0 diagnostics.
E2E: N/A — the Canary new-project jobs run setup on real runners.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop, then on the develop to main release PR.
