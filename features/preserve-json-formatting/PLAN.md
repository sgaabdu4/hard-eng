# Keep project JSON formatting when setup has nothing to add

Status: Complete

## Outcome + scope

Fix [#147](https://github.com/sgaabdu4/hard-eng/issues/147): setup and update leave `.mcp.json`, `.github/mcp.json`, `.claude/settings.json`, `.codex/hooks.json` and `.github/hooks/hard-eng.json` byte-for-byte unchanged when their content already matches what Hard Eng would write, so a formatter's layout survives every update. Files that gain an entry are still written. Non-goals: preserving a file's layout while adding an entry, or changing which entries are written.

## Repository context

Owners: `configure_mcp` in `.hooks/mcp_setup.py` and `configure_hooks` in `setup.py`; both always emit `json.dumps(current, indent=2)`. `update_plan` in `.hooks/update.py` drops only planned files whose text is identical, so any reflow becomes an update change. Reproduced: a fresh install reformatted with tab indentation → `setup.py --plan` lists all five files, and each planned file parses equal to the file on disk.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix all open Hard Eng issues, check edge cases, and merge to main through a PR.

## Acceptance + steps

- [x] A reformatted install with nothing to add → `setup.py --plan` plans none of the five JSON files; `tests/test_mcp_setup.py` and `tests/test_setup.py` prove it.
- [x] A missing MCP server or hook entry → the file is still rewritten with the entry; existing tests pass.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` on `31464e4` content (the merged baseline repair, #149) → exit 0; 17/17 gates PASS, 800 tests.
Execution: One builder; skip the write at each owner when nothing changed.

## Risks + recovery

A skipped write could hide a needed change; the comparison is on parsed content, so any added entry still writes. Revert the two conditions if an update misses an entry.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: Sandbox: fresh install reformatted with tab indentation → `setup.py --plan` plans no file changes (before the fix: all five JSON files). Removing `codebase-memory-mcp` and the `Stop` hook → only `.mcp.json` and `.claude/settings.json` are planned, both entries come back and a user-added server is kept. Without the fix, `test_install_preserves_project_and_repeats` and `test_installer_preserves_native_mcp_settings_on_rerun` fail on the rewritten files. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 802 tests.
E2E: N/A — setup planning change; the sandbox `setup.py --plan` run exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
