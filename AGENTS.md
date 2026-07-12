# Agent Rules

Read project instructions/evidence before claims or edits. Use `$hard-eng` for new features, material behavior changes, ambiguous product/UI work, or an explicit lifecycle. Work directly for small, clear fixes, questions, and mechanical edits.

For topology/callers/dependencies/routes/architecture/impact, first run `codebase-memory-mcp cli list_projects`; when missing/stale, run `codebase-memory-mcp cli index_repository '{"repo_path":"<absolute-repo>"}'`; then run `codebase-memory-mcp cli <get_architecture|search_graph|trace_path|detect_changes> '<bounded-json>'`. Use `rg` only after one failure.

For large logs/output/docs/diffs/APIs/data, use Context Mode `ctx_*`; CLI: `context-mode index <path> --source <label> --project <repo>`, then `context-mode search "<query>" --source <label> --project <repo> --limit 10`. Run `context-mode doctor` once before bounded fallback. Never edit through Context Mode.

Never launch model evals or subagents automatically. Preserve security, accessibility, and data-loss protections.
