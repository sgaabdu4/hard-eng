# Add Antigravity (agy) compatibility for hooks, MCP setup and challenge

Status: Complete

## Outcome + scope

Hard Eng supports Antigravity (`agy`) with full parity alongside Claude Code and Codex: workspace hooks (`.agents/hooks.json` for `SessionStart`, `Stop` and `PreToolUse` foreground-polling guard), workspace MCP servers (`.agents/mcp_config.json`), 3-way cross-agent fallback in `challenge` (including read-only `agy` as reviewer), and `agy` support in `release_canary.py`. Non-goals: changing `.agents/skills/` layout; modifying user-global `~/.gemini/config/` files; adding `PreInvocation` per-turn overhead for `failures.py` or a Claude-only `Artifact` hook.

## Sources + coverage

Sources: N/A — the user's chat messages are the only source.
Deliverables: None

## Repository context

Owners: `.hooks/agent_hooks.py` (hook file map, `SessionStart` and `Stop` input and output contracts), `.hooks/settings_merge.py` (per-agent and Antigravity `.agents/hooks.json` entry building, merging and output formatting), `.hooks/hard-eng.py` (early hook dispatch and Python-floor refusal), `.hooks/gate_runner.py` (CLI `agent` and `--host` choices), `setup.py` (`configure_hooks`), `.hooks/polling.py` (`PreToolUse` foreground sleep guard), `.hooks/mcp_setup.py` (`existing_servers`, `configure_mcp`, `configure_agy_mcp`), `.hooks/challenge.py` (3-way reviewer fallback, `ANTIGRAVITY_AGENT` detection, read-only `agy` reviewer command), `release_canary.py` (`agy` agent command), `.agents/hooks.json` (committed hooks for this source repository).
Same cause: N/A — new host integration for Antigravity (`agy`), not a bug fix.
Single source: `.hooks/agent_hooks.py::HOOK_FILES` owns the map of supported agents (`claude`, `codex`, `agy`) to their repository hook files; `.hooks/mcp_setup.py::detected_servers` owns the canonical server definitions shared across `.mcp.json`, `.codex/config.toml` and `.agents/mcp_config.json`; `.hooks/challenge.py::REVIEWER_ORDER` owns the cross-agent fallback chains for all three hosts.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous — the user approved the plan and chose Autonomous mode in chat on 2026-11-21, including testing on a greenfield and brownfield project in Antigravity, and approved delivering as a hotfix PR to `main` followed by joining `main` into `develop` on 2026-11-21.
Decisions:

1. Antigravity loads workspace hooks from `.agents/hooks.json`, where top-level keys are hook names (`"hard-eng"`) and `SessionStart` and `Stop` take flat handler lists while `PreToolUse` uses `{"matcher": "run_command", "hooks": [...]}`. Setup writes and merges `"hard-eng"` in `.agents/hooks.json`, preserves custom hooks and handlers, and refuses if `"hard-eng"` has `"enabled": false`.
2. Antigravity's `SessionStart` contract reads `conversationId` on stdin and outputs `{"injectSteps": [{"systemMessage": {"systemMessage": "<text>"}}]}`. Like Claude Code, Antigravity loads `AGENTS.md` and `GEMINI.md` natively but not `AGENTS.override.md`, so `SessionStart` for `agy` prompts to read `AGENTS.override.md` when present.
3. Antigravity's `Stop` contract passes `continuationActive`, `fullyIdle`, `finalModelOutput`, `parentConversationId` and `terminationReason`. Subagents (`parentConversationId` set) and `USER_CANCELED` stops return `{}` immediately. Blocking verification returns `{"decision": "continue", "reason": "<text>"}`; passing returns `{}`.
4. `.hooks/polling.py` supports Antigravity `PreToolUse` on `run_command` (`toolCall.args.CommandLine`, skipping `parentConversationId` and `IsDaemon: true`), returns `{"decision": "deny", "reason": REASON}` on polling waits, and outputs nothing when allowed (verified live: `{}` causes Antigravity to deny with an empty reason).
5. Antigravity loads workspace MCP servers from `.agents/mcp_config.json` under `{"mcpServers": ...}` using `"command"` / `"args"` or `"url"` (without `"type": "http"`). Setup reads it in `existing_servers()`, writes detected servers, preserves custom servers, and removes retired integrations (`context-mode`, `codebase-memory-mcp`).
6. `.hooks/challenge.py` uses each CLI's configured default model (no hardcoded model names) with a 3-way fallback chain (`claude` → `codex`, `agy`; `codex` → `claude`, `agy`; `agy` → `codex`, `claude`). It detects `ANTIGRAVITY_AGENT=1`, strips `ANTIGRAVITY_*` / `AGY_*` markers while preserving `GEMINI_HOME`, and runs `agy -p --disable-slash-commands --settings <read-only-json>` when `agy` is the reviewer.
7. `failures.py` is skipped for `agy` (Option A, same as Codex) to avoid per-turn `PreInvocation` overhead; `Stop` retains repeated gate failure tracking.

## Acceptance + steps

- [x] Setup writes `.agents/hooks.json` under `"hard-eng"` with flat `SessionStart` and `Stop` handlers and grouped `PreToolUse` `polling.py` on `run_command`, preserves custom named hooks and handlers, refuses `"enabled": false`, and commits `.agents/hooks.json` in this repository → `tests/test_hook_setup.py::test_hook_registrations_invoke_shared_runner`, `tests/test_hook_setup.py::test_agy_hooks_preserve_custom_hooks_and_refuse_disabled`
- [x] `hard-eng.py session agy` records the session from `conversationId`, returns `injectSteps` with a `systemMessage` step, and tells `agy` to read `AGENTS.override.md` when present → `tests/test_agent_hooks.py::test_session_reports_update_status_without_running_update`, `tests/test_agent_hooks.py::test_only_claude_and_agy_are_told_to_read_override`
- [x] `hard-eng.py stop agy` skips subagents (`parentConversationId`) and `USER_CANCELED`, honors `continuationActive`, `fullyIdle: false` and `finalModelOutput`, returns `{"decision": "continue", "reason": ...}` when verification blocks (including old Python), and returns `{}` when it passes → `tests/test_hook_setup.py::test_agy_stop_contract_maps_block_to_continue_and_respects_idle_and_continuation`, `tests/test_hook_setup.py::test_old_python_gets_a_plain_refusal_before_any_import`
- [x] `polling.py` denies Antigravity main-session foreground sleep waits on `run_command` with `{"decision": "deny", "reason": ...}` and allows subagents, daemons and non-polling commands → `tests/test_polling.py::test_agy_run_command_foreground_sleep_wait_is_denied`
- [x] Setup and MCP configuration read, write and retire `.agents/mcp_config.json` using Antigravity's native schema without `"type": "http"` → `tests/test_mcp_setup.py::test_appwrite_target_survives_repeat_setup_without_reasking`, `tests/test_mcp_setup.py::test_installer_registers_only_detected_service_mcps`
- [x] `challenge` detects `ANTIGRAVITY_AGENT=1` and `--host agy`, strips `ANTIGRAVITY_*` / `AGY_*` while keeping `GEMINI_HOME`, runs read-only `agy` when selected, and falls back across the other two CLIs when the first reviewer is unavailable or fails → `tests/test_challenge.py::test_reviewer_is_the_other_agent_of_the_running_host`, `tests/test_challenge.py::test_challenge_falls_back_to_second_reviewer_when_first_fails`, `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`
- [x] `release_canary.py` supports running `agy` in headless mode → `tests/test_release_canary.py::test_agent_command_supports_agy`
- [x] Real `agy` validation (`agy plugin validate` and Language Server `GetCustomizationStates`) accepts the generated `.agents/hooks.json` and `.agents/mcp_config.json`, and greenfield + brownfield trials run in Antigravity → N/A — one-time real tool checks per `AGENTS.override.md` and user request, recorded in Verification

## Baseline + execution

Result: Passed
Evidence: Starting commit `00f75479` on `origin/main` passed all 8 GitHub Actions checks (`hard-eng`, `hard-eng-checks`, and `hard-eng-tests 1..6`).
Execution: One builder; implemented all hooks, MCP, `challenge`, `release_canary.py` and skill updates within the 1000-line limit, ran focused tests, static gates, real `agy` tool comparisons, Reader prose check, greenfield/brownfield Antigravity trials and the Complete gate.

## Risks + recovery

- Antigravity's protojson parser for hook results rejects unknown fields and treats `{}` in `PreToolUse` as a deny; verified live against the real `agy` 1.5.14 binary and Antigravity Language Server.
- Recovery: revert the branch commits and remove `.agents/hooks.json`.

## ux_reference

N/A — no visual UI changes; CLI, hooks and MCP configuration only.

## Verification

Result: Passed
Delivery target: Merge
Delivery: Pending — hotfix PR into main with passing hard-eng, canary and release source checks, then join main into develop.
Evidence: Focused tests passed (`tests/test_hook_setup.py`, `tests/test_agent_hooks.py`, `tests/test_polling.py`, `tests/test_mcp_setup.py`, `tests/test_challenge.py`, `tests/test_release_canary.py`, `tests/test_skill_links.py`, `tests/test_requirements.py` — 342/342 after fixing the two failures below). All Python static gates passed (`ruff format --check`, `ruff check`, `complexity`, `annotations`, `pyrefly` 0 diagnostics, `vulture` 0 findings, `hot-paths` 0 findings). Real `agy` tool comparison: 5 of 5 generated project configs (`js-basic`, `flutter-mcp`, `appwrite-cloud`, `sentry-cloud`, `custom-hooks-merge`) agreed between Hard Eng and both `agy plugin validate --strict --json` (exit 0) and Antigravity Language Server `GetCustomizationStates` (`STATUS_ENABLED`). Live Antigravity hook proof: `.agents/hooks.json` `PreToolUse` denied `sleep 60` with `HE-NO-FOREGROUND-POLL` and allowed normal commands; `Stop` allowed pausing while background tasks ran (`fullyIdle: false`), blocked with `"decision": "continue"` on a formatting mismatch and exited cleanly on `continuationActive: true`. Skill prose Reader check on `git diff -- .agents/skills/`: `No findings.` Antigravity trials: greenfield Python (`feat/add-integers`, commit `26809b1`) and brownfield `itsdangerous` (`feat/sum-ints`, commits `8f504e5` and `3825f86`) both passed all 7 steps (`session agy`, `hard-eng.py check`, `stop agy` returning `{}` with `verified`, and `polling.py` denying `sleep 60` while allowing `pytest -x`). Final full `python3 .hooks/hard-eng.py check` runs on the integrated tree.
E2E: N/A — no visual user interface journey; real `agy` CLI/Language Server validation, live hook execution and greenfield/brownfield Antigravity trials prove the integration end to end.
Real service: N/A — no outside network service is called by the changed code; `agy` and Git run locally.
Retro: (1) `.hooks/polling.py` initially returned `{}` for allowed Antigravity commands, which live Antigravity `PreToolUse` treated as a deny → fixed to return empty stdout (`None`), proved live and locked in `tests/test_polling.py::test_agy_run_command_foreground_sleep_wait_is_denied`. (2) `tests/test_challenge.py::test_no_branch_point_records_not_done_without_calling_the_reviewer` failed when run inside Antigravity because it cleared `CODEX_THREAD_ID` without clearing `ANTIGRAVITY_AGENT` → updated that test to clear `ANTIGRAVITY_AGENT`. (3) Adding `agy` handling directly inside `setup.py::configure_hooks` pushed its complexity to 12 (> 10) and `.hooks/agent_hooks.py` over 1000 lines → extracted `configure_agent_hooks` and `agy_event_output` into `.hooks/settings_merge.py`; `complexity` and `HE-FILE-LENGTH` caught both immediately. (4) Initial skill prose added an unnecessary Antigravity paragraph in `integrations.md` and restated the 3 fallback chains in `challenge.md` → trimmed per `writing-great-skills`, and the Reader subagent confirmed `No findings.`
