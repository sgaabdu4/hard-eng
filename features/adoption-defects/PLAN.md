# Fix defects found while adopting Hard Eng in existing repositories

Status: Ready

## Outcome + scope

Installing and running Hard Eng in existing Flutter, Next.js and Python function repositories works without hand edits, suppressions or excludes: old-generation files are migrated, re-runs repair missing files, installed files pass the project's own formatters, and scanner gates judge only committed content and real risks. Non-goals: supporting requirements.txt-only projects as a new language flavour, Prettier-formatted vendored Markdown, and changing any consumer repository.

## Repository context

Owners: installer (`setup.py`, `.hooks/update.py`), gate generation and execution (`.hooks/gate_config.py`, `.hooks/hard-eng.py`, `.hooks/gitleaks_scan.py`), pre-push (`.hooks/ship_actions.py`), shipped skills (`.agents/`), shipping docs (`.agents/skills/he-ship/references/checks.md`). Reports came from installing the current main into several consumer repositories; each item was reproduced here before its fix, except where Verification says otherwise.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for every reported item to be fixed in one PR, without suppressions, ignores or allowlists; standing instruction: merge when green.

## Acceptance + steps

- [ ] Old-generation Hard Eng files and hook entries are removed or migrated on setup; project-owned files stay → installer tests.
- [ ] requirements.txt-only Python repositories get an exact instruction naming the directories and the uv commands → `test_requirements_only_project_is_told_how_to_declare_itself`.
- [ ] Installed `.hooks` survive a project ruff config targeting py314 with line-length 120 → `test_installed_hooks_survive_project_ruff_settings` (real ruff).
- [ ] Shipped `.agents` files and setup-written JSON pass a Biome project's own `biome ci .` → install-level Biome test.
- [ ] Re-running setup restores missing Hard Eng-owned files without overwriting project edits → installer tests.
- [ ] `hashlib.sha1(..., usedforsecurity=False)` passes the Python security gate; plain `hashlib.sha1(...)` still fails → real semgrep test.
- [ ] A pre-push over budget states elapsed time, budget, and how to fix it; a GitHub SSH origin gets an HTTPS recommendation before the checks → `test_pre_push_budget_fails_even_when_commands_pass`.
- [ ] Plan `Evidence:` errors state the same-line rule → already true since #125; reproduced, no change.
- [ ] secrets-files ignores gitignored content reached through a tracked symlink; tracked secrets still fail → gitleaks test.
- [ ] ci-security passes when a repository has no workflows; uncollectable or malformed workflows still fail → real zizmor test.

## Baseline + execution

Result: Passed
Evidence: main 649b6da passed CI and the full local check. The reported defects were reproduced here first: ruff rewrote `except (A, B):` so Python 3.12 failed to compile it; real Biome failed the shipped `.mjs` and setup-written JSON; semgrep 1.178.0 flagged `usedforsecurity=False`; zizmor 1.30.1 exited 3 with no workflows; a tracked symlink into a gitignored file was scanned.
Execution: Four parallel builders in isolated worktrees (installer, Python, Biome, scanners); the coordinator implements pre-push and integrates.

## Risks + recovery

The SHA-1 fix replaces one registry semgrep rule with a Hard Eng rule that keeps flagging plain SHA-1. It covers gates passing `p/python` as a separate argument. Nested formatter configs (`.hooks/ruff.toml`, `.agents/biome.json`) are skipped by tools run with `--config` or `--isolated`. Existing installs pick everything up through the verified updater.

## ux_reference

N/A — installer, gate and hook behaviour have no product UI.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — a fresh install into temporary Biome and Python projects, with their own formatters and gates, passes.

Delivery target: Merge
Delivery: Pending — PR, required CI and main verification.
