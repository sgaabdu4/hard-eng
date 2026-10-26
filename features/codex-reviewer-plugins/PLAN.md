# Codex reviewer starts without the user's Codex plugins

Status: Complete

## Outcome + scope

`challenge` starts the Codex reviewer with Codex plugins switched off, so the user's plugin skills, MCP tools and hooks stay out of an independent review. Non-goals: the Claude reviewer, Codex MCP servers set in `config.toml`, eval and canary Codex runs.

## Repository context

Owners: `.hooks/challenge.py` `command`; `tests/test_challenge.py`. Codex source (openai/codex 970111f, `codex-rs/features/src/lib.rs`): feature `plugins` is Stable and on by default; `--disable` rejects unknown keys, `-c features.<key>=false` does not.
Same cause: The Claude reviewer already starts with `--safe-mode` (commit 99d2926) so outside hooks stay out. Other Codex launches: `tests/agent_checks.py` uses a fresh `CODEX_HOME` that shares only the login, so no user plugins load; `release_canary.py` runs Codex sessions on purpose with the project's own setup.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous weekly reference-repo watch that Abid asked for on 2026-10-20 (build adopt/adapt items as PRs into develop, merge on green). Idea source: Compound Engineering commit aab34552.

## Acceptance + steps

- [x] A Claude host starts Codex read-only with `-c features.plugins=false` before `--cd` → `tests/test_challenge.py::test_claude_host_runs_codex_read_only_without_user_plugins_and_closed_stdin` passes; it failed before the change.

## Baseline + execution

Result: Passed
Evidence: develop dab302d CI passed; `uv run pytest tests/test_challenge.py` with only the test edit: 1 failed (argv had no plugin override), as expected.
Execution: One builder, this session.

## Risks + recovery

A Codex release that renames the `plugins` key loads plugins again and nothing fails. Recovery: the test pins the argv; a rename needs a new key here.

## ux_reference

N/A — command-line arguments only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_challenge.py`: 28 passed. `check --plan-stage Complete --base origin/develop`: every gate passed except 6 Dart/Swift tests that need `dart` and `swiftc`, which this cloud container lacks; CI has both (1,952 tests passed).
E2E: N/A — a real Codex run is not allowed in cloud sessions; the fake CLI test proves the arguments Codex receives.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` checks pass on the PR.
