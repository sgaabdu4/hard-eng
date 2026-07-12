# Codebase Memory Workflows

## Exploration

1. Run `codebase-memory-mcp cli list_projects` and use its exact project name.
2. If missing, run `codebase-memory-mcp cli index_repository '{"repo_path":"<absolute-repo>"}'` once.
3. Run one bounded `get_architecture`, `search_graph`, or `get_code_snippet` CLI query.
4. Read the returned source file before making a claim or edit.

## Tracing

1. Run bounded CLI `search_graph` to discover the exact symbol name.
2. Run CLI `trace_path` with the exact project, symbol, direction, and depth.
3. Run CLI `detect_changes` against the final tree before shipping.

## Gotchas

1. `search_graph` with `relationship: "HTTP_CALLS"` filters nodes by degree; use a bounded `query_graph` Cypher query to inspect actual edges.
2. `query_graph` caps rows; keep the query bounded and use degree filters for counts.
3. `trace_path` needs exact names; discover them with `search_graph` first.
4. `direction: "outbound"` misses callers; use `both` when impact is unclear.
5. Check `has_more` and use a bounded `offset`; never dump every page.
6. On one CLI failure, report it and use the smallest `rg` fallback. Never start the MCP transport.
