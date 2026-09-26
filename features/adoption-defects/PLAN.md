# Fix defects found while adopting Hard Eng in existing repositories

Status: Complete

## Outcome + scope

Installing and running Hard Eng in existing Flutter, Next.js and Python function repositories works without hand edits, suppressions or excludes: old-generation files are migrated, re-runs repair missing files, installed files pass the project's own formatters, and scanner gates judge only committed content and real risks. Non-goals: supporting requirements.txt-only projects as a new language flavour, Prettier-formatted vendored Markdown, and changing any consumer repository.

## Repository context

Owners: installer (`setup.py`, `.hooks/update.py`), gate generation and execution (`.hooks/gate_config.py`, `.hooks/hard-eng.py`, `.hooks/gitleaks_scan.py`), pre-push (`.hooks/ship_actions.py`), shipped skills (`.agents/`), shipping docs (`.agents/skills/he-ship/references/checks.md`). Reports came from installing the current main into several consumer repositories; each item was reproduced here before its fix, except where Verification says otherwise.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for every reported item to be fixed in one PR, without suppressions, ignores or allowlists; standing instruction: merge when green.

## Acceptance + steps

- [x] Every old-generation Hard Eng file carrying the generated mark and every hook command mentioning `.hard-eng` is removed on setup, rerun and update, edited or not; project-owned files stay → `tests/test_adoption.py` install, rerun and update tests. An automatic update refuses locally edited old files; rerunning setup removes them without committing the edits.
- [x] requirements.txt-only Python repositories get an exact instruction naming the directories and the uv commands → `test_requirements_only_project_is_told_how_to_declare_itself`.
- [x] Installed `.hooks` survive a project ruff config targeting py314 with line-length 120 → `test_installed_hooks_survive_project_ruff_settings` (real ruff).
- [x] Shipped `.agents` files and setup-written JSON pass a Biome project's own `biome ci .` → `test_setup_json_stays_in_the_project_biome_layout`, `test_written_json_matches_the_project_formatter_layout`; setup JSON follows the root Biome config's indent and line width.
- [x] Re-running setup restores missing Hard Eng-owned files without overwriting project edits → `test_setup_rerun_restores_missing_installed_files`, `test_setup_rerun_leaves_local_settings_edits_uncommitted`.
- [x] `hashlib.sha1(..., usedforsecurity=False)` passes the Python security gate; plain `hashlib.sha1(...)` still fails → `test_python_security_gate_replaces_only_the_registry_sha1_rule` (real semgrep).
- [x] A pre-push over budget states elapsed time, budget, and how to fix it; a GitHub SSH origin gets an HTTPS recommendation before the checks → `test_pre_push_budget_fails_even_when_commands_pass`.
- [x] Plan `Evidence:` errors state the same-line rule → already true since #125; reproduced, no change.
- [x] secrets-files ignores gitignored content reached through a tracked symlink; tracked secrets still fail → `test_tracked_link_to_an_ignored_local_secret_is_not_scanned`.
- [x] ci-security passes when a repository has no workflows; uncollectable or malformed workflows still fail → `test_ci_security_passes_only_when_no_workflows_exist_to_collect` (real zizmor).
- [x] Claude Code v2.1.277+ reads `AGENTS.md` directly, so setup writes the `CLAUDE.md` import only when a project `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` would replace `AGENTS.md`, and retires a committed `CLAUDE.md` that holds only that import; `.claude/skills` links stay because Claude Code loads skills only there → `test_native_instruction_paths_preserve_project_rules`, `test_install_retires_a_claude_md_that_only_imports_agents_md`.

## Baseline + execution

Result: Passed
Evidence: main 649b6da passed CI and the full local check. The reported defects were reproduced here first: ruff rewrote `except (A, B):` so Python 3.12 failed to compile it; real Biome failed the shipped `.mjs` and setup-written JSON; semgrep 1.178.0 flagged `usedforsecurity=False`; zizmor 1.30.1 exited 3 with no workflows; a tracked symlink into a gitignored file was scanned.
Execution: Four parallel builders in isolated worktrees (installer, Python, Biome, scanners); the coordinator implements pre-push and integrates.

## Risks + recovery

The SHA-1 fix replaces one registry semgrep rule with a Hard Eng rule that keeps flagging plain SHA-1. It covers gates passing `p/python` as a separate argument. Nested formatter configs (`.hooks/ruff.toml`, `.agents/biome.json`) are skipped by tools run with `--config` or `--isolated`. Existing installs pick everything up through the verified updater. Claude Code before v2.1.277, its first session after upgrading from one, or with the `agents-md` plugin disabled reads no Hard Eng rules without a `CLAUDE.md`. Parent-directory `CLAUDE.md` files are checked only on the machine running setup; another machine with one needs the **Project instructions** setting `claude-md-and-agents-md`. Setup JSON reads only the root Biome config: `extends`, path `overrides` and Prettier options are not followed.

## ux_reference

N/A — installer, gate and hook behaviour have no product UI.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` → exit 0 on the final commit. Each new regression failed on the code before its fix. Codex adversarial review ran 15 rounds; its old-generation edge cases were settled by the user's decision to remove all old wiring outright rather than preserve partial legacy setups.
E2E: Passed — fresh installs into temporary projects: a Biome project configured for spaces passes `biome ci .` (29 files); a Python project with ruff py314 and line-length 120 passes `ruff check` and `ruff format --check`, and Hard Eng's format, lint, types, annotations, security, dead-code, dependencies and both secrets gates pass there.

Delivery target: Merge
Delivery: Pending — PR, required CI and main verification.
