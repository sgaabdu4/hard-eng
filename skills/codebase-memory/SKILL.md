---
name: codebase-memory
description: Use codebase graph for symbols, callers, deps, routes, impact, dead code, Cypher, search_graph, trace_path.
---

# Codebase Memory — Knowledge Graph Tools

Graph tools return precise structural results in ~500 tokens vs ~80K for grep.

MCP bridge names these tools as `mcp__codebase_memory_mcp__<tool>`.
Use the prefixed tool names when available; use `mcp_call` only as fallback.

## Quick Decision Matrix

Read `references/tool-catalog.md` for tool selection, graph queries, edge types, and Cypher examples.

## Workflow Details

Read `references/workflows.md` for exploration, tracing, and gotchas.

## Quality Analysis

- Dead code: `mcp__codebase_memory_mcp__search_graph(max_degree=0, exclude_entry_points=true)`
- High fan-out: `mcp__codebase_memory_mcp__search_graph(min_degree=10, relationship="CALLS", direction="outbound")`
- High fan-in: `mcp__codebase_memory_mcp__search_graph(min_degree=10, relationship="CALLS", direction="inbound")`
