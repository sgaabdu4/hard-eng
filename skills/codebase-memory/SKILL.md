---
name: codebase-memory
description: Use codebase graph for symbols, callers, deps, routes, impact, dead code, Cypher, search_graph, trace_path.
---

# Codebase Memory — Knowledge Graph Tools

Graph tools return precise structural results in ~500 tokens vs ~80K for grep.

MCP bridge names these tools as `mcp__codebase_memory_mcp__<tool>`.
Use the prefixed tool names when available; use `mcp_call` only as fallback.

## Quick Decision Matrix

| Question | MCP tool call |
|----------|----------|
| Who calls X? | `mcp__codebase_memory_mcp__trace_path(direction="inbound")` |
| What does X call? | `mcp__codebase_memory_mcp__trace_path(direction="outbound")` |
| Full call context | `mcp__codebase_memory_mcp__trace_path(direction="both")` |
| Find by name pattern | `mcp__codebase_memory_mcp__search_graph(name_pattern="...")` |
| Dead code | `mcp__codebase_memory_mcp__search_graph(max_degree=0, exclude_entry_points=true)` |
| Cross-service edges | `mcp__codebase_memory_mcp__query_graph` with Cypher |
| Impact of local changes | `mcp__codebase_memory_mcp__detect_changes()` |
| Risk-classified trace | `mcp__codebase_memory_mcp__trace_path(risk_labels=true)` |
| Text search | `mcp__codebase_memory_mcp__search_code` or Grep |

## Exploration Workflow
1. `mcp__codebase_memory_mcp__list_projects` — check if project is indexed
2. `mcp__codebase_memory_mcp__get_graph_schema` — understand node/edge types
3. `mcp__codebase_memory_mcp__search_graph(label="Function", name_pattern=".*Pattern.*")` — find code
4. `mcp__codebase_memory_mcp__get_code_snippet(qualified_name="project.path.FuncName")` — read source

## Tracing Workflow
1. `mcp__codebase_memory_mcp__search_graph(name_pattern=".*FuncName.*")` — discover exact name
2. `mcp__codebase_memory_mcp__trace_path(function_name="FuncName", direction="both", depth=3)` — trace
3. `mcp__codebase_memory_mcp__detect_changes()` — map git diff to affected symbols

## Quality Analysis
- Dead code: `mcp__codebase_memory_mcp__search_graph(max_degree=0, exclude_entry_points=true)`
- High fan-out: `mcp__codebase_memory_mcp__search_graph(min_degree=10, relationship="CALLS", direction="outbound")`
- High fan-in: `mcp__codebase_memory_mcp__search_graph(min_degree=10, relationship="CALLS", direction="inbound")`

## 14 MCP Tools
`index_repository`, `index_status`, `list_projects`, `delete_project`,
`search_graph`, `search_code`, `trace_path`, `detect_changes`,
`query_graph`, `get_graph_schema`, `get_code_snippet`, `get_architecture`,
`manage_adr`, `ingest_traces`

## Edge Types
CALLS, HTTP_CALLS, ASYNC_CALLS, IMPORTS, DEFINES, DEFINES_METHOD,
HANDLES, IMPLEMENTS, OVERRIDE, USAGE, FILE_CHANGES_WITH,
CONTAINS_FILE, CONTAINS_FOLDER, CONTAINS_PACKAGE

## Cypher Examples (for query_graph)
```
MATCH (a)-[r:HTTP_CALLS]->(b) RETURN a.name, b.name, r.url_path, r.confidence LIMIT 20
MATCH (f:Function) WHERE f.name =~ '.*Handler.*' RETURN f.name, f.file_path
MATCH (a)-[r:CALLS]->(b) WHERE a.name = 'main' RETURN b.name
```

## Gotchas
1. `search_graph(relationship="HTTP_CALLS")` filters nodes by degree — use `query_graph` with Cypher to see actual edges.
2. `query_graph` has a 200-row cap — use `search_graph` with degree filters for counting.
3. `trace_path` needs exact names — use `search_graph(name_pattern=...)` first.
4. `direction="outbound"` misses cross-service callers — use `direction="both"`.
5. Results default to 10 per page — check `has_more` and use `offset`.
