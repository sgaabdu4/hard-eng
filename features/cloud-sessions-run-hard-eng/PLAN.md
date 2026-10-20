# Cloud sessions run Hard Eng in its own repository

Status: Ready

## Outcome + scope

A cloud session that clones this repository loads Hard Eng's hooks, skills and attribution setting from committed files. `check` and `ship` reject Claude attribution when the committed settings turn it off. Non-goals: changes to what setup installs in other projects; closing or rebuilding PRs 320-323, which their own threads do.

## Repository context

Owners: `setup.py` `configure_hooks` and `prepare_skill_links` write `.claude/settings.json`, `.codex/hooks.json` and `.claude/skills/*` in installed projects. This repository's `.claude/settings.json` held only `outputStyle`, so cloud sessions had no SessionStart or Stop hook, no `/he` skills and default attribution. PRs 320-323 carried attribution trailers and skipped the Stop gate and `ship --stage ready`.
Checks: `.hooks/hard-eng.py` `check` runs branch validators; `.hooks/shipping.py` `verify` reads the PR body.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. Abid gave standing approval to push, open PRs and decide, then report. He asked for all cloud sessions to follow Hard Eng and for no Claude attribution.

## Acceptance + steps

- [ ] This repository holds exactly the hooks, attribution setting and skill links that setup writes → `tests/test_agent_hooks.py::test_source_repository_installs_hard_eng_on_itself`.
- [ ] `check` fails on a commit with a Claude trailer or a Claude author when committed settings turn commit attribution off, and passes otherwise → `tests/test_agent_hooks.py::test_check_rejects_claude_attribution_when_settings_turn_it_off`.
- [ ] `ship --stage ready` fails on a PR body with the Claude Code footer when committed settings turn PR attribution off → `tests/test_agent_hooks.py::test_ready_ship_rejects_a_pr_body_with_claude_attribution`.
- [ ] The SessionStart hook runs in a cloud container and reports gate status → N/A — needs a new cloud session after merge; recorded in Verification.

## Baseline + execution

Result: Passed
Evidence: On `fbbb031`, `configure_hooks` on this repository returned changes for `.claude/settings.json` and `.codex/hooks.json`, and `.claude/skills` did not exist. The new self-install test fails on the old settings file.
Execution: One builder on branch `claude/project-thread-a6djkq`.

## Risks + recovery

The Stop hook runs `check` at the end of each cloud turn. If the cloud network blocks tool installs, the gate blocks and says why. Recovery: fix the environment's network or setup script; never weaken the gate.

## ux_reference

N/A — agent configuration and checks; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the real proof is a new cloud session after merge, which this branch cannot start.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
