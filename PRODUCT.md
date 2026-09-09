# Hard Eng

Repository-owned engineering checks for developers and coding agents.

## Register

product

## Users

Developers using coding agents who need consistent checks and clear evidence that a change works.

## Problem

An agent can report completion after an incomplete test run, overlook scanner failures, or check a working-tree fix while pushing different committed code.

## Product Purpose

Run the repository's declared checks and stop when a required check fails. Keep the flow small enough to understand and run directly.

The installer adds shared instructions, skills, gate code and the required agent configuration directly to an existing project. The project owns its application code and actual check commands. The shared CLI validates those commands' results and checks pushed revisions. CI is published and required on protected `main`; [DECISION.md](DECISION.md) tracks native verification and remaining gaps.

## Brand Personality / Tone

Plain, concise and factual. State the failed check and useful evidence. Never present an unrun check as a pass.

## Boundaries

- Support the agreed Python, JavaScript/TypeScript and Dart/Flutter scope; implementation status varies by language.
- Require only work needed for the user's request and meaningful verification.
- Add no custom hash framework, result-cache framework or legacy migration machinery.
- Tool results cannot certify product judgment, semantic necessity or test quality.

## Stack

- [AGENTS.md](AGENTS.md): working rules.
- [DESIGN.md](DESIGN.md): interface guidance.
- [DECISION.md](DECISION.md): agreed scope and completion checkboxes.
- [hard-eng.gates.json](hard-eng.gates.json): this repository's commands.

## Commands

From the root of the project that needs Hard Eng, run:

```sh
curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh
```

The installer configures Codex, Claude and Copilot. Skills live once in `.agents/skills/`: Codex and Copilot discover them directly, and Claude gets links in `.claude/skills/`. The gate code lives in `.agents/hard-eng/`. Existing project instructions and configuration are preserved; no Git submodule or nested Git repository is installed.

Configuration affects only this project. Claude enables the native Context Mode plugin in `.claude/settings.json` and installs it with project scope when the Claude CLI is available. Codex uses `.codex/config.toml` and `.codex/hooks.json` for Context Mode's MCP server and hooks, because its native plugin installer enables plugins user-wide. Codebase Memory is an MCP server: Claude reads `.mcp.json`, Codex reads `.codex/config.toml`, and Copilot reads `.github/mcp.json`. Native clients keep their downloaded plugin files in their own caches.

Setup does not require a prewritten gate configuration. The agent studies the project and adapts the bundled language templates to its actual commands. Normal implementation remains blocked until setup and readiness pass. Installation selects the latest main revision with a successful workflow. Restart the agent and trust the project's configuration and hooks through its native controls before working.

Installed projects use `python3 .agents/hard-eng/bin/hard-eng session` for updates/readiness and `python3 .agents/hard-eng/bin/hard-eng check` for gates. This source checkout uses `python3 bin/hard-eng check`.
