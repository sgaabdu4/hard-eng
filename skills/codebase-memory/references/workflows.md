# Codebase Memory Workflows

## Exploration

1. `mcp__codebase_memory_mcp__list_projects` - check if project is indexed.
2. `mcp__codebase_memory_mcp__get_graph_schema` - understand node/edge types.
3. `mcp__codebase_memory_mcp__search_graph(label="Function", name_pattern=".*Pattern.*")` - find code.
4. `mcp__codebase_memory_mcp__get_code_snippet(qualified_name="project.path.FuncName")` - read source.

## Tracing

1. `mcp__codebase_memory_mcp__search_graph(name_pattern=".*FuncName.*")` - discover exact name.
2. `mcp__codebase_memory_mcp__trace_path(function_name="FuncName", direction="both", depth=3)` - trace.
3. `mcp__codebase_memory_mcp__detect_changes()` - map git diff to affected symbols.

## Gotchas

1. `search_graph(relationship="HTTP_CALLS")` filters nodes by degree; use `query_graph` with Cypher to see actual edges.
2. `query_graph` has a 200-row cap; use `search_graph` with degree filters for counting.
3. `trace_path` needs exact names; use `search_graph(name_pattern=...)` first.
4. `direction="outbound"` misses cross-service callers; use `direction="both"`.
5. Results default to 10 per page; check `has_more` and use `offset`.
