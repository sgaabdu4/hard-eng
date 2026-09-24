# Keep project MCP config formatting when no server is added

Status: Complete

## Outcome + scope

Fix [#147](https://github.com/sgaabdu4/hard-eng/issues/147): every setup or update run rewrites `.mcp.json` and `.github/mcp.json` with `json.dumps(indent=2)`, even when no server is added. That reflows a project-formatted file, for example splitting a short `args` array across lines, and the project's own JSON format check then fails. Keep the file's existing text when every server is already present; serialize only when a server is added. Non-goals: preserving formatting when a server is added, and `.codex/config.toml`, which is already appended to rather than reserialized.

## Repository context

Owner: `configure_mcp` in `.hooks/mcp_setup.py`, which always set `changes[name] = json.dumps(current, indent=2) + "\n"`. Consumers: `setup.install` writes every entry, and `update` drops entries whose text equals the file. `test_installer_preserves_native_mcp_settings_on_rerun` relies on both MCP keys staying in `changes` and on a repeat run producing identical changes, so keeping the key with the file's own text fits better than dropping it. A missing file always gains the default servers, so it is always serialized.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix this issue and open a PR; merging is not authorized.

## Acceptance + steps

- [x] A compact-formatted `.mcp.json` and `.github/mcp.json` that already list every server come back byte-identical after `configure_mcp` output is written → new `test_mcp_setup_keeps_project_formatting_unless_a_server_is_added`, red before the fix (file reflowed to two-space indentation).
- [x] A file missing a server is still updated with it, and the complete file stays byte-identical → same test.
- [x] Existing MCP, setup, update and hook setup behavior is unchanged → `tests/test_mcp_setup.py`, `tests/test_setup.py`, `tests/test_updates.py`, `tests/test_hook_setup.py` pass.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: main at `ba19011`, CI run 35919600611 success. The new test on the unfixed code → 1 failed; the rewritten file differs at the first indent (two spaces instead of the project's tab).
Execution: Single session on `fix/mcp-config-formatting`; one conditional in `configure_mcp`.

## Risks + recovery

A file that gains a server is still reserialized with two-space indentation, as before. Revert the conditional if a caller needs normalized JSON on every run.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_mcp_setup.py` + `tests/test_setup.py` + `tests/test_updates.py` + `tests/test_hook_setup.py` → 145 passed. Ruff format and lint clean. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 801 tests.
E2E: N/A — installer change; the new test runs `configure_mcp` and writes its output the way setup does, then compares file bytes.

Delivery target: PR
Delivery: Pending — PR checks green; merge left to the maintainer.
