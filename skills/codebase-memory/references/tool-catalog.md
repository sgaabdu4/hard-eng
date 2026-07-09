# Codebase Memory Tool Catalog

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

## MCP Tools

`index_repository`, `index_status`, `list_projects`, `delete_project`, `search_graph`, `search_code`, `trace_path`, `detect_changes`, `query_graph`, `get_graph_schema`, `get_code_snippet`, `get_architecture`, `manage_adr`, `ingest_traces`

## Edge Types

CALLS, HTTP_CALLS, ASYNC_CALLS, IMPORTS, DEFINES, DEFINES_METHOD, HANDLES, IMPLEMENTS, OVERRIDE, USAGE, FILE_CHANGES_WITH, CONTAINS_FILE, CONTAINS_FOLDER, CONTAINS_PACKAGE

## Cypher Examples

```cypher
MATCH (a)-[r:HTTP_CALLS]->(b) RETURN a.name, b.name, r.url_path, r.confidence LIMIT 20
MATCH (f:Function) WHERE f.name =~ '.*Handler.*' RETURN f.name, f.file_path
MATCH (a)-[r:CALLS]->(b) WHERE a.name = 'main' RETURN b.name
```
