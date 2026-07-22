# SDK Routing

Use only the official Appwrite SDK for the runtime. Do not hand-roll Appwrite
REST calls unless the SDK lacks the endpoint, or an isolated tested
`Client.call` works around SDK model parsing.

## Packages

| Runtime | Official package |
|---------|------------------|
| Web TypeScript/JavaScript / React | `appwrite` |
| Node.js / Deno / TypeScript SSR | `node-appwrite` |
| Flutter client | `appwrite` |
| Dart server / Functions | `dart_appwrite` |
| Python | `appwrite` |

## Call Style

- TypeScript SDK calls use object parameters.
- Python SDK calls should use keyword arguments. Use positional args only when
  maintaining existing code or when the user explicitly asks.
- Dart SDK calls use named parameters.

## Client vs Server

- Client/mobile SDKs use account sessions and user-scoped APIs.
- Server SDKs use API keys for admin operations.
- SSR uses two clients: an admin client for session creation or privileged work,
  and a per-request session client with `setSession(...)`.

## Shared Rules

- Resource ID allocation/retry reuse = [Critical Rule 4](../SKILL.md#critical-rules).
- Use TablesDB, not deprecated Collections/Databases document APIs.
- Use `Query.select()` for relationships.
- Use cursor pagination for large lists.
- Use `Permission` and `Role` helpers, not raw permission strings.
- Initialize SDK clients outside warm Function handlers where the runtime allows.
