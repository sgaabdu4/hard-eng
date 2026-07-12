# Codebase Memory CLI Catalog

Every example uses the local CLI transport:

```text
codebase-memory-mcp cli <tool> '<bounded-json>'
```

Never translate these calls to `mcp__*`, `mcp_call`, or a Codex MCP entry.

## Quick Decision Matrix

| Question | CLI call |
|----------|----------|
| Who calls X? | `codebase-memory-mcp cli trace_path '{"project":"<project>","function_name":"<X>","direction":"inbound","depth":3}'` |
| What does X call? | `codebase-memory-mcp cli trace_path '{"project":"<project>","function_name":"<X>","direction":"outbound","depth":3}'` |
| Full call context | `codebase-memory-mcp cli trace_path '{"project":"<project>","function_name":"<X>","direction":"both","depth":3}'` |
| Find by name pattern | `codebase-memory-mcp cli search_graph '{"project":"<project>","name_pattern":"<bounded-pattern>","limit":20}'` |
| Dead code | `codebase-memory-mcp cli search_graph '{"project":"<project>","max_degree":0,"exclude_entry_points":true,"limit":20}'` |
| Cross-service edges | `codebase-memory-mcp cli query_graph '{"project":"<project>","query":"<bounded-cypher>"}'` |
| Impact of local changes | `codebase-memory-mcp cli detect_changes '{"project":"<project>"}'` |
| Risk-classified trace | `codebase-memory-mcp cli trace_path '{"project":"<project>","function_name":"<X>","direction":"both","depth":3,"risk_labels":true}'` |
| Exact known text/path | `rg` directly; graph lookup is unnecessary |

## CLI tools

Use only the bounded read/index subset needed for repository work:
`index_repository`, `index_status`, `list_projects`, `search_graph`,
`search_code`, `trace_path`, `detect_changes`, `query_graph`,
`get_graph_schema`, `get_code_snippet`, and `get_architecture`.

## Edge Types

CALLS, HTTP_CALLS, ASYNC_CALLS, IMPORTS, DEFINES, DEFINES_METHOD, HANDLES, IMPLEMENTS, OVERRIDE, USAGE, FILE_CHANGES_WITH, CONTAINS_FILE, CONTAINS_FOLDER, CONTAINS_PACKAGE

## Cypher Examples

```cypher
MATCH (a)-[r:HTTP_CALLS]->(b) RETURN a.name, b.name, r.url_path, r.confidence LIMIT 20
MATCH (f:Function) WHERE f.name =~ '.*Handler.*' RETURN f.name, f.file_path
MATCH (a)-[r:CALLS]->(b) WHERE a.name = 'main' RETURN b.name
```
