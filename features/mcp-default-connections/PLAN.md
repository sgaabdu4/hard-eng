# Connect the default MCP servers in Claude Code and Codex

Status: Complete

## Outcome + scope

In an installed project, the Codebase Memory and Context Mode servers that setup
writes connect without manual steps once the folder is trusted:

- Claude Code approves the `.mcp.json` servers setup owns through the project
  `.claude/settings.json`, instead of leaving them at "Pending approval".
- Codex allows a cold `pnpm dlx` start of the generated Context Mode and
  Codebase Memory entries, instead of its 10 s default startup timeout.
- Setup does not add a second Codebase Memory or Context Mode server when the
  project already runs that package under another name.

Non-goals: a fixed install path for Codebase Memory, Codex plugin hooks for
Context Mode, Copilot timeouts, and user-level configuration.

## Repository context

`.hooks/mcp_setup.py` `configure_mcp` writes `.mcp.json`, `.github/mcp.json`
and `.codex/config.toml`. It adds missing server names only and never edits an
existing entry. `setup.py` `configure_hooks` writes the Claude project settings
before `configure_mcp` runs.

Claude Code connects a project `.mcp.json` server only when it is approved; it
honours `enabledMcpjsonServers` from the shared project settings once the folder
is trusted. Codex waits `startup_timeout_sec` (default 10 s) for a server. A cold
`pnpm dlx context-mode@latest` start measured 16 s; warm starts measured 0.3 s.
Codebase Memory runs one daemon per user, and a client launched from another
install path gets no answer from it, so a second entry for the same package
fails to connect.

## Decisions + authorization

Blockers: None
The user asked for these changes, followed by an adversarial review loop before
the PR. Claude approval covers every `.mcp.json` server name setup owns
(`codebase-memory-mcp` and the detected Dart, Marionette, Appwrite and Sentry
servers), matching Codex and Copilot, which run them after folder trust without
per-server approval. Existing approvals are kept, and a user rejection
(`disabledMcpjsonServers`) still wins. The Codex timeout is 60 s. It is added to
new entries and to existing entries whose settings exactly match the earlier
generated default; any other entry is left unchanged.

## Baseline + execution

Result: Passed
Evidence: `uv run --locked pytest -q tests/test_mcp_setup.py tests/test_updates.py tests/test_setup.py` → 164 passed on `431dd64`.

## Acceptance + steps

- [x] Setup approves its `.mcp.json` servers in the Claude project settings, keeps existing approvals and does not repeat a rerun.
- [x] New Codex entries for Context Mode and Codebase Memory carry `startup_timeout_sec = 60`; an entry in the earlier generated shape gains it; a customised entry is unchanged.
- [x] An existing server that runs `codebase-memory-mcp` or `context-mode` under another name prevents a duplicate in every config file.
- [x] The exact candidate passes the Complete check.

## Risks + recovery

Approving by name also approves a user's own entry kept under a setup-owned
name; that entry is the project's chosen server for that service. Remove the
added names from `enabledMcpjsonServers` to require approval again.

## ux_reference

N/A — installer configuration with no product UI.

## Verification

Result: Passed
Evidence: `uv run --locked pytest -q tests/test_mcp_setup.py tests/test_updates.py tests/test_setup.py` → 167 passed; the new and updated tests fail without the fix. Real Claude client: after approval, `codebase-memory-mcp` moved from `Pending approval` to starting in a trusted checkout and in a worktree of a trusted repository, and stayed pending in a worktree of an untrusted repository. Codex adversarial review (`gpt-6-astra`) approved with no findings.
E2E: N/A — installer configuration; covered by setup tests against real files.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification.
