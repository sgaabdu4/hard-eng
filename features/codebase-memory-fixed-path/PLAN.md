# Launch Codebase Memory from one fixed path

Status: Complete

## Outcome + scope

Every installed project on a machine runs the same Codebase Memory binary, so
all Claude Code, Codex and Copilot sessions reach the one per-user daemon:

- Setup points the Codebase Memory entry in `.mcp.json`, `.github/mcp.json`
  and `.codex/config.toml` at a Hard Eng launcher instead of `pnpm dlx`.
- The launcher installs a pinned version once into a per-user directory and
  runs that binary; later starts reuse it.
- An install interrupted by a host's startup timeout still completes, so the
  next session starts without downloading again.
- Setup migrates only its own earlier `pnpm dlx codebase-memory-mcp@latest`
  entries; custom entries stay unchanged.

Non-goals: changing user-level client configuration, removing older installed
versions, Context Mode launch, and Windows support.

## Repository context

`.hooks/mcp_setup.py` `configure_mcp` writes the three MCP files; `runs_package`
detects a server that already runs the package. Setup installs every
`.hooks/*.py` file, and the Sentry and Appwrite launchers already rely on
repository-relative commands.

The daemon (0.11.0) answers only clients whose binary resolves to the same real
path; a symlink to its binary connected in 3.0 s. `pnpm dlx` rotates its cache
directory, so each rotation or second install fails to connect
(DeusData/codebase-memory-mcp#2398). A pinned install into one directory took
1 s for `pnpm add --ignore-scripts` plus 32 s for the verified binary download.
Claude Code's default startup timeout is 30 s and it sends SIGTERM to the server
process only; Codex entries allow 60 s.

## Decisions + authorization

Blockers: None
The user chose one fixed path until the upstream daemon issue is fixed. The
version is pinned in the launcher, because each install of `@latest` could
resolve to a different path; Hard Eng updates move every project to the same
pin. The install directory is `${XDG_DATA_HOME:-~/.local/share}/hard-eng/codebase-memory-mcp/<version>`.
This is a per-user install owned by the launcher; it adds no user-level client
configuration.

## Baseline + execution

Result: Passed
Evidence: `uv run --locked pytest -q tests/test_mcp_setup.py tests/test_updates.py tests/test_setup.py` → 167 passed on `970c4f3`.

## Acceptance + steps

- [x] Fresh setup writes the launcher command for Codebase Memory in all three files, with the 60 s Codex timeout.
- [x] Setup replaces the earlier generated `pnpm dlx` Codebase Memory entries (with or without the Codex timeout) and leaves custom entries unchanged; a rerun changes nothing.
- [x] Launches from two repositories, including from a subdirectory, run the same installed binary, install only when it is missing, and keep stdout for the MCP protocol.
- [x] Real MCP clients started from two repositories against one isolated daemon both initialize; a client from a different install path does not.
- [x] The exact candidate passes the Complete check.

## Risks + recovery

The first start after a version change downloads about 300 MB and can exceed
Claude's 30 s startup timeout; that session reports a failed connection and the
next one connects. A daemon from another install path, such as a user-level
`pnpm dlx` entry, still blocks the launcher until that entry is removed or
pointed at the same binary. Older version directories stay on disk. Recovery:
delete the install directory to force a fresh install, or revert the entries to
`pnpm dlx`.

## ux_reference

N/A — MCP launcher with no product UI.

## Verification

Result: Passed
Evidence: New migration and launcher tests fail without the change and pass with it; the fresh-install test checks the launcher entries and file. Real 0.11.0 package with an isolated daemon: a cold launch stopped with SIGTERM after 5 s still completed its install (65 s) with no staging leftovers.
E2E: Passed — MCP `initialize` through the launcher from two repositories against one isolated daemon: 7.5 s (daemon start) and 1.9 s; a client from a different install path got the rendezvous error after 32 s.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification.
