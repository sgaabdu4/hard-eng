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

The CLI validates gate configuration, runs configured checks, invokes managed scanners and checks pushed revisions. Repository-local installation, updates, MCP readiness, agent configuration and a shared CI workflow are implemented. Publication and native agent enforcement verification remain outstanding; [DECISION.md](DECISION.md) tracks the remaining gaps.

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

After adapting the [language templates](skills/he/templates/) to a target repository, run `./setup.sh /path/to/repository --agent codex` from this checkout. Choose `claude` or `copilot` instead, or repeat `--agent` for multiple adapters. Installation requires a published successful main workflow; this rebuild is not published yet.

Installed projects use `python3 .hard-eng/bin/hard-eng session` for updates/readiness and `python3 .hard-eng/bin/hard-eng check` for gates. This source checkout uses `python3 bin/hard-eng check`.
