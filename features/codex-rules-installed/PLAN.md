# Include Codex rules file in verified installed scaffold paths

Status: Complete

## Outcome + scope

`.hooks/update.py` includes `agent_hooks.CODEX_RULES_FILE` (`.codex/rules/hard-eng.rules`) in `INSTALLED_FILES`, so an update from an earlier Hard Eng revision that creates `.codex/rules/hard-eng.rules` passes `maybe_installed`, `check_scaffold_update`, `installed_update_paths`, and `change_size.update_only`, while a tampered `.codex/rules/hard-eng.rules` is still refused by `release_installed` via `update_plan`. Non-goals: changing the generated Codex rule text or weakening the exact-match verification.

## Sources + coverage

Sources: N/A — escaped bug discovered on `main` (`7b641594`) when upgrading installed repositories from earlier releases that lacked `.codex/rules/hard-eng.rules`.

## Repository context

Owners: `.hooks/update.py` (`INSTALLED_FILES`, `maybe_installed`, `release_installed`, `check_scaffold_update`); `.hooks/agent_hooks.py` (`CODEX_RULES_FILE`, `codex_rule_change`); `tests/test_scaffold_replay.py`.
Same cause: `agent_hooks.CODEX_RULES_FILE` was added to `setup.py` / `update_plan` without adding it to `update.INSTALLED_FILES`, so `maybe_installed` and `release_installed`'s `allowed` set rejected it whenever an upgrade introduced the file.
Single source: `agent_hooks.CODEX_RULES_FILE` is imported from `agent_hooks` into `update.INSTALLED_FILES`, which feeds both `maybe_installed` and `release_installed`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — escaped bug fix on `main`, authorized in chat on 2026-11-21.

## Acceptance + steps

- [x] An update that creates `.codex/rules/hard-eng.rules` from a base without it passes `maybe_installed`, `check_scaffold_update`, `installed_update_paths`, and `change_size.update_only` → `tests/test_scaffold_replay.py::test_an_update_that_adds_codex_rules_stays_a_verified_scaffold_update`.
- [x] A tampered or symlinked `.codex/rules/hard-eng.rules` is refused by `check_scaffold_update` → `tests/test_scaffold_replay.py::test_an_update_that_adds_codex_rules_stays_a_verified_scaffold_update`.

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`f5e7cb0c`), `test_an_update_that_adds_codex_rules_stays_a_verified_scaffold_update` failed at `assert all(update.maybe_installed(name) for name in changed)` before the `.hooks/update.py` edit.
Execution: Single builder in a linked worktree off `origin/develop`.

## Risks + recovery

Low risk: `release_installed` already verifies `.codex/rules/hard-eng.rules` byte-for-byte via `update_plan` (`codex_rule_change`). Recovery: revert the commit.

## ux_reference

N/A — updater hook fix only; no UI.

## Verification

Result: Passed
Evidence: Failing-first test failed before the edit and passed after adding `agent_hooks.CODEX_RULES_FILE` to `INSTALLED_FILES`; full `tests/test_scaffold_replay.py` and `hard-eng.py check --quick --base origin/develop --plan-stage Complete` passed.
E2E: N/A — hook unit and replay tests cover the updater contract.
Real service: N/A — `INSTALLED_FILES` path membership calls no outside service.
Retro: Escaped bug on `main` (`7b641594`): existing scaffold-update tests ran `setup.py` at the base commit so `.codex/rules/hard-eng.rules` already existed before the update diff. Permanent prevention: `tests/test_scaffold_replay.py::test_an_update_that_adds_codex_rules_stays_a_verified_scaffold_update` upgrades from a base without `.codex/rules/hard-eng.rules` and proves both acceptance and tamper refusal.

Delivery target: Merge
Delivery path: PR into develop.
Delivery: Pending — PR checks green, independent review complete, and merged into develop.
