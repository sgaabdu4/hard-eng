# Copilot-specific Rules

Follow `~/.copilot/AGENTS.md` for harness-agnostic agent rules. These rules cover Copilot CLI only.

## MCP boot check

- Copilot user MCP config must be `~/.copilot/mcp-config.json`; `~/.copilot/.mcp.json` is not loaded as the user-level config
- Copilot workspace MCP config must be `.mcp.json` with top-level `mcpServers`; `.vscode/mcp.json` is no longer supported
- Keep the canonical config at `~/.agents/mcp-config.json` and symlink it to `~/.copilot/mcp-config.json`
- The config must include `codebase-memory-mcp` and `context-mode`. If either tool is absent in a new session, run `copilot mcp list` and restart Copilot after fixing the symlink
- `AGENTS.md` can enforce behavior only after tools are exposed; it cannot make Copilot load missing MCP servers
