---
name: codebase-memory
description: Use the local Codebase Memory CLI for repository topology, symbols, callers, dependencies, routes, architecture, impact, dead code, or bounded graph queries. Never use its MCP transport.
---

# Codebase Memory CLI

Invoke only `codebase-memory-mcp cli <tool> '<bounded-json>'`. The executable's
upstream name contains `mcp`, but that does not authorize an MCP server, MCP
tool call, MCP configuration entry, or fallback bridge.

- Read [tool-catalog.md](references/tool-catalog.md) to select the smallest
  bounded CLI query.
- Read [workflows.md](references/workflows.md) for indexing, tracing, impact,
  pagination, and failure handling.
- Use `rg` directly for an exact known path/text lookup, or after one reported
  CLI failure. Never edit through Codebase Memory.
