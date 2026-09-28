# Enable Context Mode for Claude sessions in this repository

Status: Complete

## Outcome + scope

Claude Code sessions in this repository and its worktrees load the Context Mode
plugin from tracked project settings, the same way setup enables it in
installed projects. No hooks, MCP servers or Codex configuration change.

## Repository context

Setup writes `extraKnownMarketplaces` and `enabledPlugins` for Context Mode into
an installed project's `.claude/settings.json`. This repository has no project
settings, so its sessions only had Context Mode while it was enabled in user
settings. With the plugin enabled per project instead, sessions here lost it.
Worktrees receive only tracked files, so an untracked local settings file
cannot cover them.

## Decisions + authorization

Blockers: None
The user asked for a project settings file that enables Context Mode here. The
file carries only the two keys setup already writes for installed projects, in
the order Claude Code writes them.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` passed on `431dd64` before the change.

## Acceptance + steps

- [x] Project settings enable `context-mode@context-mode` from the `mksglu/context-mode` marketplace.
- [x] With the user-level entry set to `false`, `claude mcp list` in this checkout shows the Context Mode plugin server connected.
- [x] The exact candidate passes the Complete check.

## Risks + recovery

Contributors are prompted to install the plugin when they trust the folder.
Remove `.claude/settings.json` to stop enabling it.

## ux_reference

N/A — agent configuration with no product UI.

## Verification

Result: Passed
Evidence: `claude mcp list` in this checkout reported `plugin:context-mode:context-mode … ✔ Connected` after the project-scope install; before the file it listed no Context Mode server. `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed on the candidate.
E2E: N/A — no product journey changes.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification.
