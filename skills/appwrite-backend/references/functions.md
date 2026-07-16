# Functions Best Practices

## Architecture

**Group functions by domain.** Each function own one domain — not one operation, not everything.
Use official SDK packages only. For self-hosted Appwrite `1.9.x`, pin Dart Functions/server code to `dart_appwrite: 25.1.0`; for Appwrite Cloud, use the latest stable SDK supported by the runtime.

```
✅ api-users          — all user endpoints (CRUD, profile, settings)
✅ api-orders         — order creation, status, cancellation
✅ api-notifications  — email, push, SMS triggers
✅ process-images     — resize, convert, thumbnail
✅ scheduled-cleanup  — daily/weekly maintenance tasks
❌ handle-everything  — one monolith doing all domains
❌ create-user        — one function per operation
```

**Warm-start advantage:** More requests per function = instances stay warm. Function handling 50 user ops gets 50x traffic vs one handling just "create user" — rarely cold-starts.

### Route Handling Inside Domain Functions

```dart
Future<dynamic> main(final context) async {
    final path = context.req.path;
    final method = context.req.method;

    if (method == 'GET' && path == '/users') return listUsers(context);
    if (method == 'POST' && path == '/users') return createUser(context);
    if (method == 'GET' && path.startsWith('/users/')) return getUser(context);
    if (method == 'PUT' && path.startsWith('/users/')) return updateUser(context);
    if (method == 'DELETE' && path.startsWith('/users/')) return deleteUser(context);

    return context.res.json({'error': 'Not found'}, statusCode: 404);
}
```

### When to Split

Split when domain function has ops w/ vastly different resource needs, exceeds timeout, or needs different API key scopes.

---

## Cold Start Optimization

### Language Choice

Cloud runtime note: Appwrite Cloud supports Dart `3.12` for Functions. Self-hosted runtimes depend on the installed Appwrite image and `_APP_FUNCTIONS_RUNTIMES`.

| Language | Cold Start | Use When |
|----------|-----------|----------|
| Dart | Fastest | User-facing (compiled, native SDK) |
| Node.js + ESBuild | Fast | npm ecosystem needed |
| Python | Slowest | Data processing, ML |

**Bundle interpreted languages** to single file:

```bash
npx esbuild src/index.ts --bundle --platform=node --outfile=dist/index.js
```

**Keep deps minimal.** Every dep adds cold start time.

### Specifications

| Workload | CPU | Memory |
|----------|-----|--------|
| Text processing, CRUD | Low | 128MB |
| Image processing | High | 512MB+ |
| ML inference | High | 1GB+ |

---

## Handler Pattern

Init SDK + services **outside handler** (warm-start). Refresh dynamic API key each call — changes per execution.

### Dart

```dart
Client? _client;
TablesDB? _tablesDB;

void _ensureInit(dynamic context) {
  final apiKey = (context.req.headers['x-appwrite-key'] ?? '') as String;

  if (_client != null) {
    _client!.setKey(apiKey);
    return;
  }

  _client = Client()
      .setEndpoint(Platform.environment['APPWRITE_FUNCTION_API_ENDPOINT']!)
      .setProject(Platform.environment['APPWRITE_FUNCTION_PROJECT_ID']!)
      .setKey(apiKey);
  _tablesDB = TablesDB(_client!);
}

Future<dynamic> main(final context) async {
    _ensureInit(context);
    final rows = await _tablesDB!.listRows(
        databaseId: 'db', tableId: 'items',
        queries: [Query.limit(10)], total: false);
    return context.res.json({'items': rows.rows});
}
```

### Python

```python
client = None
tables_db = None

def _ensure_init(context):
    global client, tables_db
    api_key = context.req.headers.get('x-appwrite-key', '')

    if client is not None:
        client.set_key(api_key)
        return

    client = Client()
    client.set_endpoint(os.environ['APPWRITE_FUNCTION_API_ENDPOINT'])
    client.set_project(os.environ['APPWRITE_FUNCTION_PROJECT_ID'])
    client.set_key(api_key)
    tables_db = TablesDB(client)

def main(context):
    _ensure_init(context)
    rows = tables_db.list_rows(
        database_id='db', table_id='items',
        queries=[Query.limit(10)], total=False)
    return context.res.json({'items': rows['rows']})
```

### TypeScript

```typescript
let client: Client | null = null;
let tablesDB: TablesDB | null = null;

function ensureInit(context: any) {
    const apiKey = context.req.headers['x-appwrite-key'] ?? '';

    if (client) {
        client.setKey(apiKey);
        return;
    }

    client = new Client()
        .setEndpoint(process.env.APPWRITE_FUNCTION_API_ENDPOINT!)
        .setProject(process.env.APPWRITE_FUNCTION_PROJECT_ID!)
        .setKey(apiKey);
    tablesDB = new TablesDB(client);
}

export default async ({ req, res }: any) => {
    ensureInit({ req });
    const rows = await tablesDB!.listRows({
        databaseId: 'db', tableId: 'items',
        queries: [Query.limit(10)], total: false});
    return res.json({ items: rows.rows });
};
```

---

## Request/Response API

Appwrite Function handlers expose the same concepts across Dart, Python, and
TypeScript:

| Concept | Dart | Python | TypeScript |
|---------|------|--------|------------|
| Raw body | `context.req.body` | `context.req.body` | `req.body` |
| JSON body | `context.req.bodyJson` | `context.req.body_json` | `req.bodyJson` |
| Headers | `context.req.headers` | `context.req.headers` | `req.headers` |
| Method | `context.req.method` | `context.req.method` | `req.method` |
| Path | `context.req.path` | `context.req.path` | `req.path` |
| Query | `context.req.query` | `context.req.query` | `req.query` |
| JSON response | `context.res.json(...)` | `context.res.json(...)` | `res.json(...)` |
| Text response | `context.res.text(...)` | `context.res.text(...)` | `res.text(...)` |
| Empty response | `context.res.empty()` | `context.res.empty()` | `res.empty()` |
| Redirect | `context.res.redirect(...)` | `context.res.redirect(...)` | `res.redirect(...)` |

Validate every body/query/header value before using it.

---

## Input Validation & Responses

> **Security:** All user input from `context.req.bodyJson` untrusted. Always validate types, sanitize strings, enforce length limits before processing.

```dart
Future<dynamic> main(final context) async {
    if (context.req.method != 'POST') {
        return context.res.json({'error': 'Method not allowed'}, statusCode: 405);
    }

    // ⚠️ UNTRUSTED INPUT — validate before use
    final body = context.req.bodyJson;
    final email = _sanitizeString(body['email']);
    if (email == null || !_isValidEmail(email)) {
        return context.res.json({'error': 'Invalid email'}, statusCode: 400);
    }

    final password = _sanitizeString(body['password']);
    if (password == null || password.length < 8 || password.length > 128) {
        return context.res.json({'error': 'Invalid password'}, statusCode: 400);
    }

    try {
        final user = await account.create(
            userId: ID.unique(), email: email, password: password);
        return context.res.json({'userId': user.$id});
    } on AppwriteException catch (e) {
        return context.res.json({'error': e.message}, statusCode: e.code ?? 500);
    }
}

// Sanitization helpers
String? _sanitizeString(dynamic value) {
    if (value is! String) return null;
    return value.trim().substring(0, value.length.clamp(0, 1000));
}

bool _isValidEmail(String email) {
    return email.length <= 254 && RegExp(r'^[^@]+@[^@]+\.[^@]+$').hasMatch(email);
}
```

---

## Security

### API Keys

Appwrite auto-generates short-lived API key per execution from function's **scopes** (Console → Settings → Scopes). Use `context.req.headers['x-appwrite-key']` — no manual key mgmt.

```
✅ rows.read only for a read function
✅ teams.read + teams.write + rows.read + rows.write for squad ops
❌ All scopes for every function
```

### Execute Permissions

```
['users']              — any authenticated user
['user:abc123']        — specific user only
['team:teamABC']       — team members
[]                     — server/event/schedule only
```

### Enforce Authorization Server-Side

```dart
Future<dynamic> main(final context) async {
    final userId = context.req.headers['x-appwrite-user-id'];
    if (userId == null || userId.isEmpty) {
        return context.res.json({'error': 'Unauthorized'}, statusCode: 401);
    }

    final row = await tablesDB.getRow(
        databaseId: 'db', tableId: 'orders', rowId: orderId);
    if (row.data['userId'] != userId) {
        return context.res.json({'error': 'Forbidden'}, statusCode: 403);
    }
}
```

---

## Environment Variables

Use variables for configuration + secrets; never track values in source/manifests.

- scope precedence = project → function/site → Appwrite-injected
- secret value = unreadable from Console/API after creation
- secret status = one-way; secret → non-secret requires delete + recreate
- variable mutation = next deployment only; redeploy + runtime smoke required
- read-back = exact key/ID/count + secret metadata, never secret value
- deployment workflow = validate candidate → upsert metadata → deploy → smoke

CLI workflow → [appwrite-cli.md](appwrite-cli.md#function-variables).
Production sequencing → [production-migrations.md](production-migrations.md#function--variable-cutover).

```dart
final stripeKey = Platform.environment['STRIPE_SECRET_KEY']!;
```

### Built-In Variables & Headers

| Name | Source | Description |
|------|--------|-------------|
| `APPWRITE_FUNCTION_API_ENDPOINT` | Env var | API endpoint (auto-injected) |
| `APPWRITE_FUNCTION_PROJECT_ID` | Env var | Project ID (auto-injected) |
| `x-appwrite-key` | `req.headers` | Dynamic API key (scoped, short-lived) |
| `x-appwrite-user-id` | `req.headers` | Caller's user ID (empty for server calls) |
| `x-appwrite-user-jwt` | `req.headers` | Caller's JWT (client-SDK executions) |

---

## Related

- [functions-advanced.md](functions-advanced.md) — Caching, events, scheduling, CI/CD, anti-patterns
- [realtime.md](realtime.md) — Event-driven subscriptions
- [cost-optimization.md](cost-optimization.md) — Reducing execution costs
