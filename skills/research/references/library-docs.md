# Library Documentation

1. Read project manifest + lockfile → library name + installed/target version.
2. Resolve: `CTX7_TELEMETRY_DISABLED=1 npx --yes ctx7 library <name> "<specific task + version>"`.
3. Select closest name + matching version + strongest reputation/coverage; record Context7 ID.
4. Query: `CTX7_TELEMETRY_DISABLED=1 npx --yes ctx7 docs <library-id> "<specific API question>"`.
5. Material/current claim → verify against linked official vendor docs or source repo.
6. Finish with version + command + source URL + answer, or explicit Context7 limitation.

- Context7 = library-doc retrieval only; never repository topology or general web research.
- No MCP setup + no permanent install + no `ctx7 setup` unless explicitly requested.
- Ambiguous result/version mismatch → do not guess; use official docs/search.
