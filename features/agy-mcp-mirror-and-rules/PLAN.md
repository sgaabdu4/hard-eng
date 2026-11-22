# Mirror compatible custom MCP servers into Antigravity config and update Antigravity docs

Status: Complete

## Outcome + scope

Mirror compatible non-retired custom MCP servers from `.mcp.json` and `.codex/config.toml` into `.agents/mcp_config.json` while preserving existing Antigravity entries and detected-service precedence, and update stale Claude+Codex-only documentation to include Antigravity. Non-goals: editing any submodule under `.agents/skill-sources/`, modifying user-global `~/.gemini/config/mcp_config.json`, or mirroring unsupported `sse` transports, Codex-only env-expanded HTTP auth, or pending managed `appwrite`/`sentry` entries.

## Sources + coverage

Sources: N/A — the user's request is the only source.
Deliverables: None

## Repository context

Owners: `.hooks/mcp_setup.py` (`detected_servers`, `configure_mcp`, `configure_agy_mcp`, `_mirror_agy_servers`, and Claude/Codex translation helpers), `tests/test_mcp_setup.py`, `AGENTS.md`, `.agents/skills/he/references/integrations.md`, `.agents/skills/e2e/references/flutter.md`.
Same cause: Earlier fix `features/add-agy-compatibility/PLAN.md` added `.agents/mcp_config.json` support for Hard Eng's four auto-detected servers (`appwrite`, `dart`, `marionette`, `sentry`) and updated most docs (helped detected-service parity, left project-custom servers unmirrored and a few stale Claude+Codex references behind). Searched outside `.agents/skill-sources/`, `features/`, and `tests/` for `\.codex/config\.toml`, `\.mcp\.json`, `Claude + Codex`, `Claude and Codex`, and `Claude or Codex`, and fixed every stale Hard Eng-owned copy together (`AGENTS.md`, `.agents/skills/he/references/integrations.md`, `.agents/skills/e2e/references/flutter.md`, `.hooks/mcp_setup.py` `retire_copilot_hooks`; `setup.py` Codex `[features]`, `retire_copilot_mcp`, and `release_canary.py`'s default `AGENTS` docstring remain intentionally scoped to what those checks run).
Single source: `.hooks/mcp_setup.py::configure_agy_mcp` and `_mirror_agy_servers` own Antigravity workspace MCP mirroring, reusing `detected_servers`, `retired_server`, `_copy_stdio_fields`, `_copy_agy_common_fields`, and `_merge_codex_tool_filters` with no duplicated translation logic; `AGENTS.md` owns shared project rules across Claude, Codex and Antigravity; `.agents/skills/he/references/integrations.md` owns per-host MCP setup guidance; `.agents/skills/e2e/references/flutter.md` owns Marionette pin update paths. Searched `.hooks/`, `setup.py`, `AGENTS.md`, and `.agents/skills/` outside `.agents/skill-sources/`; no stale duplicate remains.

## Decisions + authorization

Blockers: None
Handoff: Approval
Review declined: Mapping Codex tool_timeout_sec to Antigravity timeoutSeconds cannot preserve separate startup_timeout_sec and tool_timeout_sec deadlines :: Antigravity's mcp_config.json schema exposes only a single timeoutSeconds field for both startup and tool calls; mirroring uses max(tool_timeout_sec, startup_timeout_sec or Codex's 10-second default) so startup is never cut short below the Codex startup deadline. Stated schema limit.
Authority: Autonomous — the user explicitly authorized implementing, verifying, committing, pushing, opening and merging the PR to `develop`, and releasing to `main` on 2026-11-22.
Decisions:

1. Preserve existing non-retired keys in `.agents/mcp_config.json` verbatim before adding `detected` servers and mirroring custom servers, so user-owned Antigravity config is never overwritten and reruns remain idempotent.
2. Skip pending managed `appwrite` and `sentry` services (detected in `integrated_services` with no valid resolved target) during custom mirroring so external launchers or secret-bearing entries stay pending across hosts just as in `.codex/config.toml`.
3. Mirror compatible `.mcp.json` entries (stripping `"type"`, normalizing `"serverUrl"` to `"url"`, omitting empty optional containers, and skipping `sse`/unknown transports or ambiguous combined `command`+`url` entries) and carry over Codex `disabled_tools` / `enabled_tools` only when missing from the mirrored `.mcp.json` entry.
4. Mirror Codex-only entries (`command` stdio or `url` Streamable HTTP without `bearer_token_env_var` or `env_http_headers`), mapping `enabled: False` to `disabled: True`, `http_headers` to `headers`, `disabled_tools`/`enabled_tools` to camelCase, and positive `tool_timeout_sec` to integer `timeoutSeconds` via `math.ceil` (matching `agy` 1.5.14 Go struct `mcp.McpServer`, which rejects float `timeoutSeconds` and array `tools`).

## Acceptance + steps

- [x] Mirror compatible stdio and Streamable HTTP custom servers from `.mcp.json` into `.agents/mcp_config.json`, strip `"type"`, normalize `"serverUrl"` to `"url"`, omit empty optional containers, skip `sse`/unknown/ambiguous/retired servers, and remain idempotent on rerun → `tests/test_mcp_setup.py::test_agy_mcp_mirrors_compatible_claude_servers_and_skips_unsupported`
- [x] Carry over Codex `disabled_tools`/`enabled_tools` onto servers mirrored from `.mcp.json` only when absent, mirror compatible Codex-only stdio and HTTP servers with field mapping (`http_headers`, `enabled: false`, `tool_timeout_sec`), and skip Codex HTTP servers using `bearer_token_env_var` or `env_http_headers` as well as servers already declared unsupported in `.mcp.json` → `tests/test_mcp_setup.py::test_agy_mcp_carries_codex_tool_filters_and_mirrors_codex_only_servers`
- [x] Preserve existing `.agents/mcp_config.json` entries verbatim, keep `detected` precedence over `.mcp.json`/`.codex/config.toml`, keep pending `appwrite`/`sentry` entries unmirrored, and never mirror entries from Git-ignored `.mcp.json` or `.codex/config.toml` files → `tests/test_mcp_setup.py::test_agy_mcp_preserves_existing_entries_and_detected_precedence`, `tests/test_mcp_setup.py::test_agy_mcp_skips_gitignored_mcp_sources`, `tests/test_mcp_setup.py::test_appwrite_does_not_reuse_external_launcher`, `tests/test_mcp_setup.py::test_sentry_unsupported_stdio_target_stays_pending_for_missing_hosts`
- [x] Update stale Claude+Codex-only docs (`AGENTS.md`, `.agents/skills/he/references/integrations.md`, `.agents/skills/e2e/references/flutter.md`) and pass an independent Reader prose review → `tests/test_skill_links.py::test_distributed_skill_links_resolve`, plus independent Reader subagent check returning `No findings.` recorded in Verification
- [x] Compare `.hooks/mcp_setup.py` output against real `agy` 1.5.14 (`agy plugin validate --strict --json` and live `agy acp`) on 6 concrete hand-made inputs → N/A — one-time real tool check per `AGENTS.override.md`, recorded in Verification (6/6 agree)

## Baseline + execution

Result: Passed
Evidence: Starting commit `00dfff6f` on `origin/develop` passed GitHub Actions `Hard Eng` and `Canary` on `develop`, and `uv run pytest tests/test_mcp_setup.py` passed (`41 passed in 6.02s`) before edits. Escaped-bug reproduction: before fixing `.hooks/mcp_setup.py`, `uv run pytest tests/test_mcp_setup.py -q` failed on all 3 new regression tests (`3 failed, 41 passed`) because `.agents/mcp_config.json` omitted custom servers from `.mcp.json` and `.codex/config.toml`.
Execution: Single builder on branch `fix/agy-mcp-mirror-and-rules` off `origin/develop`; wrote failing-first unit tests, implemented mirroring in `.hooks/mcp_setup.py`, updated Antigravity docs, verified with real `agy` 1.5.14 (`agy plugin validate` and live `agy acp`), passed independent Reader prose review, and ran full `hard-eng.py check --plan-stage Complete` and `challenge`.

## Risks + recovery

- Custom `.mcp.json` or `.codex/config.toml` servers that rely on client-specific header interpolation outside Antigravity's native schema may still need manual adjustment in `.agents/mcp_config.json`, which setup preserves verbatim once present.
- Recovery: revert the merged PR commit(s) on `develop`.

## ux_reference

N/A — CLI/hook MCP configuration and Markdown skill/rule documentation only; no visual UI surface.

## Verification

Result: Passed
Evidence: Focused tests passed (`tests/test_mcp_setup.py`, `tests/test_setup.py`, `tests/test_adoption.py`, `tests/test_hook_setup.py`, `tests/test_skill_links.py`, `tests/test_requirements.py` — 223/223 passed, and 44/44 in `tests/test_mcp_setup.py` after final typing tweak). Static checks passed (`ruff format --check`, `ruff check`, `complexity`, `annotations`, `pyrefly` 0 diagnostics, `vulture` 0 findings across full repo paths, `hot-paths` 0 findings). Real `agy` 1.5.14 comparison: 6 of 6 hand-made inputs agreed between `.hooks/mcp_setup.py` and real `agy` (`agy plugin validate --strict --json` returned exit 0 with 4 servers and 0 warnings/errors on the generated config, and exit 1 with unknown-field warnings on raw `type: "sse"` and `bearer_token_env_var`; live two-turn `agy acp` spawned `custom-stdio` with `args` and `DEMO_TOKEN=ok`, `filtered-stdio` hiding `blocked_tool` via `disabledTools`, `preserved-agy` verbatim instead of `.mcp.json`'s conflicting entry, and connected to `custom-http` over Streamable HTTP with `X-Demo-Header: present`, while sending 0 requests to skipped `sse-only` and `codex-bearer`). Independent Reader prose review on `AGENTS.md`, `.agents/skills/he/references/integrations.md`, and `.agents/skills/e2e/references/flutter.md`: `No findings.` after rewriting two dense sentences in `integrations.md`. Full integrated `hard-eng.py check --plan-stage Complete` runs on the final tree.
E2E: N/A — no visual UI journey; real `agy` 1.5.14 validation (`agy plugin validate --strict --json`) and live two-turn `agy acp` MCP loading prove the runtime contract end to end.
Real service: N/A — no outside network service is called by the changed code; local loopback HTTP/stdio test probes, `agy`, and Git run locally.
Retro: (1) Escaped bug on `origin/develop` (`configure_agy_mcp` omitted custom servers from `.mcp.json` and `.codex/config.toml`) → `tests/test_mcp_setup.py::test_agy_mcp_mirrors_compatible_claude_servers_and_skips_unsupported`, `tests/test_mcp_setup.py::test_agy_mcp_carries_codex_tool_filters_and_mirrors_codex_only_servers`, `tests/test_mcp_setup.py::test_agy_mcp_preserves_existing_entries_and_detected_precedence`. (2) Real `agy plugin validate` probe showed `McpServer.tools` requires an object (not a list), `McpServer.timeoutSeconds` requires an int (rejecting `30.5`), and setting both `command` and `url` errors → guarded in `_copy_agy_common_fields`, `_timeout_seconds`, `_agy_server_from_claude`, and `_agy_server_from_codex`, locked by the tests above. (3) `pyrefly` flagged `set[LiteralString]` invariance on `pending` and `vulture` flagged unused `detected_servers` after an intermediate `_resolve_servers` split → kept `detected_servers(root, services=None)` as single owner with explicit `pending: set[str]` (`None — existing pyrefly and vulture focused checks caught both immediately`). (4) Reader subagent flagged two dense sentences in `.agents/skills/he/references/integrations.md` → split into plain sentences naming `bearer_token_env_var` and `env_http_headers` and separating new-server vs newly-opened-session behavior (`No findings.` on re-check; `writing-great-skills` Reader step caught it before commit). (5) Full `hard-eng.py check` caught `AGENTS.md` reaching 3925 bytes (> 3921 cap in `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`), two duplicated fixture dicts in `tests/test_mcp_setup.py` (`jscpd`), and an unrelated hidden-`TMPDIR` test isolation bug in `tests/test_ci_setup.py` (where `temporary_root()` fell back to `/tmp` when `tmp_path` lived below a hidden folder) → tightened `AGENTS.md` line 12 to 3910 bytes (re-verified by Reader subagent: `No findings.`), deduplicated the test dicts in `tests/test_mcp_setup.py`, and pinned `tool_setup.VISIBLE_TEMP` to `tmp_path` in `tests/test_ci_setup.py` as its own commit (`tests/test_ci_setup.py::test_native_tool_bootstrap_preserves_ci_sdk_executables`). (6) Independent `challenge` review by Codex caught mirroring from Git-ignored `.mcp.json`/`.codex/config.toml`, widening empty `enabled_tools = []`/`enabledTools = []` allowlists, mirroring Codex `environment_id` remote stdio servers locally, dropping `headersHelper`/`http_headers_helper`, and clamping `startup_timeout_sec` below `tool_timeout_sec` → fixed all five in `.hooks/mcp_setup.py` with regression cases in `tests/test_mcp_setup.py::test_agy_mcp_skips_gitignored_mcp_sources`, `tests/test_mcp_setup.py::test_agy_mcp_mirrors_compatible_claude_servers_and_skips_unsupported`, and `tests/test_mcp_setup.py::test_agy_mcp_carries_codex_tool_filters_and_mirrors_codex_only_servers`.

Delivery target: Merge
Delivery: Pending — required remote proof.
