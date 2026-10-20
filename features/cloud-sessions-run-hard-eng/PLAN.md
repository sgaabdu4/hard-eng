# Cloud sessions run Hard Eng in its own repository

Status: Complete

## Outcome + scope

A cloud session that clones this repository loads Hard Eng's hooks, skills and attribution setting from committed files. `check` and `ship` reject Claude attribution when the committed settings turn it off. The cloud GitHub proxy appends a Claude footer to every PR body it writes, so a `pr-text` workflow removes it; setup installs that workflow wherever it installs Hard Eng CI. Non-goals: changes to what setup installs in other projects; closing or rebuilding PRs 320-323, which their own threads do.

## Repository context

Owners: `setup.py` `configure_hooks` and `prepare_skill_links` write `.claude/settings.json`, `.codex/hooks.json` and `.claude/skills/*` in installed projects. This repository's `.claude/settings.json` held only `outputStyle`, so cloud sessions had no SessionStart or Stop hook, no `/he` skills and default attribution. PRs 320-323 carried attribution trailers and skipped the Stop gate and `ship --stage ready`.
Checks: `.hooks/hard-eng.py` `check` runs branch validators; `.hooks/shipping.py` `verify` reads the PR body.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. Abid gave standing approval to push, open PRs and decide, then report. He asked for all cloud sessions to follow Hard Eng and for no Claude attribution.

## Acceptance + steps

- [x] This repository holds exactly the hooks, attribution setting and skill links that setup writes → `tests/test_agent_hooks.py::test_source_repository_installs_hard_eng_on_itself`.
- [x] `check` fails on a commit with a Claude trailer or a Claude author when committed settings turn commit attribution off, and passes otherwise → `tests/test_agent_hooks.py::test_check_rejects_claude_attribution_when_settings_turn_it_off`.
- [x] `ship --stage ready` fails on a PR body with the Claude Code footer when committed settings turn PR attribution off → `tests/test_agent_hooks.py::test_ready_ship_rejects_a_pr_body_with_claude_attribution`.
- [x] The PR-text workflow removes the proxy's footer and keeps other text → `tests/test_agent_hooks.py::test_pr_text_workflow_removes_the_claude_footer_the_proxy_appends`.
- [x] Text that only names the rule passes the attribution check → `tests/test_agent_hooks.py::test_attribution_check_allows_text_that_only_names_the_rule`.
- [x] An installed project's update adds the PR-text workflow; a project without Hard Eng CI gets none → `tests/test_husky_setup.py::test_shell_bootstrap_installs_verified_main`.
- [x] The SessionStart hook runs in a cloud container and reports gate status → N/A — needs a new cloud session after merge; recorded in Verification.

## Baseline + execution

Result: Passed
Evidence: On `fbbb031`, `configure_hooks` on this repository returned changes for `.claude/settings.json` and `.codex/hooks.json`, and `.claude/skills` did not exist. The new self-install test fails on the old settings file.
Execution: One builder on branch `claude/project-thread-a6djkq`.

## Risks + recovery

The Stop hook runs `check` at the end of each cloud turn. If the cloud network blocks tool installs, the gate blocks and says why. Recovery: fix the environment's network or setup script; never weaken the gate.

## ux_reference

N/A — agent configuration and checks; no product appearance.

## Verification

Result: Passed
Evidence: The three new tests pass. Each fails when its code is removed: the self-install test on the old settings file; the attribution tests when the pattern search is disabled. Full suite: 1731 passed, 9 failed; the 9 need Dart, Swift or signal timing and fail on the base too. Ruff format, lint, complexity, annotations, pyrefly (0 diagnostics), vulture, jscpd (0 clones) and offline zizmor pass. Removing the setup call fails the update test. An Opus review found a crash on zero or unknown bases, broad patterns and a wrong error type; all three are fixed and tested. The SessionStart hook ran here and reported `Gates: ok`. After the skill links were written, this session listed the `he*` skills.
Not checked: `check` stops at tool install in this container. The agent proxy returns 403 for `api.github.com/repos/<tool>/releases` and for `mise.jdx.dev`, so gitleaks, osv-scanner, shellcheck, actionlint and uv do not install. CI runs those gates.
E2E: N/A — the real proof is a new cloud session after merge, which this branch cannot start.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
