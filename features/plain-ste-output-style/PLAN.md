# Plain STE output style

Status: Complete

## Outcome + scope

Hard Eng ships a "Plain STE" Claude output style: replies in about 80% ASD-STE100, short by default. Setup writes `outputStyle: "Plain STE"` into the project's `.claude/settings.json` only when the key is missing. The style has about 130 words. It replaces the built-in Concise style (about 250 words) where a user set that, so the prompt shrinks; with no style set it adds about 130 words. The `AGENTS.md` output line gets the same concrete limits for Codex, which has no output styles. This repository uses the style too. Non-goals: the user's global settings, a reply-checking Stop hook, Codex equivalents beyond the `AGENTS.md` line.

## Repository context

Owners: the scaffold glob in `.hooks/update.py` `scaffold_files` already installs `.claude/rules/*.md`; `maybe_installed` lists the paths an update may write; `setup.py` `configure_hooks` owns project Claude settings defaults. Custom styles drop Claude Code's coding instructions unless `keep-coding-instructions: true`, and project settings override user settings (https://code.claude.com/docs/en/output-styles).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user found replies confusing because the global Concise style overrode the `AGENTS.md` STE line. They approved a STE output style plus a clearer `AGENTS.md` rule, asked that it live in Hard Eng rather than global settings, and asked that tokens not increase. Shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Fresh project settings gain `outputStyle: "Plain STE"`; a project's own `outputStyle` is kept; the installed style keeps coding instructions → `test_claude_settings_default_fable_advisor_plain_style_and_no_attribution`.
- [x] Install and update copy `.claude/output-styles/*.md` like `.claude/rules/*.md` → the settings test reads the installed style; update uses the same scaffold glob as the rules.
- [x] `AGENTS.md` names the limits: one idea per sentence, at most 20 words, active voice, common words, no jargon or idioms.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Branch started from `origin/main` at `d2d394f4`, clean tree. Focused `tests/test_hook_setup.py tests/test_updates.py` → 73 passed with the change.
Execution: Single builder.

## Risks + recovery

The style overrides a user's own global style in these projects. Recovery: set `outputStyle` in `.claude/settings.local.json`. Style rules are instructions, not enforcement; replies can still drift. Recovery: the optional Stop hook, discussed separately.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `pytest tests/test_hook_setup.py tests/test_updates.py` → 73 passed. `check --plan-stage Ready` → exit 0, 1463 tests passed.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0.
E2E: N/A — static style text copied by the existing scaffold; its install and update tests cover delivery.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
