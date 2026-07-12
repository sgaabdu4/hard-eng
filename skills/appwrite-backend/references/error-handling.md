# Error Handling

## Contents

- Rate Limiting
- Dev Keys
- Common Error Codes
- Typed Error Handling
- Timeout Handling
- Related

## Rate Limiting

Rate limits hit Client SDKs. Server SDKs w/ API keys bypass.

### Response Headers

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max req per window |
| `X-RateLimit-Remaining` | Req left in window |
| `X-RateLimit-Reset` | Unix ts when window reset |

### 429 Response

```json
{
    "message": "Too many requests",
    "code": 429
}
```

### Exponential Backoff

```dart
// Dart
Future<T> withRetry<T>(Future<T> Function() operation, {int maxRetries = 3}) async {
    for (var attempt = 0; attempt < maxRetries; attempt++) {
        try {
            return await operation();
        } on AppwriteException catch (e) {
            if (e.code != 429 || attempt == maxRetries - 1) rethrow;
            
            final delay = Duration(seconds: (1 << attempt)); // 1, 2, 4 seconds
            await Future.delayed(delay);
        }
    }
    throw Exception('Max retries exceeded');
}

// Usage
final result = await withRetry(() => tablesDB.createRow(...));
```

```python
# Python
import time
from appwrite.exception import AppwriteException

def with_retry(operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return operation()
        except AppwriteException as e:
            if e.code != 429 or attempt == max_retries - 1:
                raise
            
            delay = 2 ** attempt  # 1, 2, 4 seconds
            time.sleep(delay)
    
    raise Exception('Max retries exceeded')

# Usage
result = with_retry(lambda: tables_db.create_row(...))
```

```typescript
// TypeScript
async function withRetry<T>(
    operation: () => Promise<T>,
    maxRetries = 3,
): Promise<T> {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            return await operation();
        } catch (e) {
            if (e.code !== 429 || attempt === maxRetries - 1) throw e;
            
            const delay = Math.pow(2, attempt) * 1000; // 1, 2, 4 seconds
            await new Promise(r => setTimeout(r, delay));
        }
    }
    throw new Error('Max retries exceeded');
}

// Usage
const result = await withRetry(() => tablesDB.createRow({...}));
```

---

## Dev Keys

Bypass rate limits in dev.

1. Console → Project Settings → Dev keys → Add key
2. Add header to req:

```dart
// Dart - Client SDK only
final client = Client()
    .setEndpoint('https://cloud.appwrite.io/v1')
    .setProject('PROJECT_ID')
    .addHeader('X-Appwrite-Dev-Key', 'your-dev-key');
```

**Never in prod.** Dev keys expose app to abuse.

---

## Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 | Bad request | Check req structure |
| 401 | Unauthorized | Check API key/session |
| 403 | Forbidden | Check perms |
| 404 | Not found | Verify resource exists |
| 409 | Conflict | ID exists |
| 429 | Rate limited | Backoff |
| 500 | Server error | Retry, contact support |

---

## Typed Error Handling

`AppwriteException` exposes structured fields. Log enough for debugging without
leaking secrets:

| SDK | Fields |
|-----|--------|
| Dart | `message`, `code`, `type`, `response` |
| Python | `message`, `code`, `type`, `response` |
| TypeScript | `message`, `code`, `type`, `response` |

Python fields are available as `e.message`, `e.code`, `e.type`, and
`e.response`.

```dart
// Dart
try {
    await tablesDB.createRow(...);
} on AppwriteException catch (e) {
    switch (e.code) {
        case 409:
            // Row already exists - update instead
            await tablesDB.updateRow(...);
            break;
        case 429:
            // Rate limited - back off
            await Future.delayed(Duration(seconds: 2));
            break;
        case 404:
            // Resource not found
            throw RowNotFoundError(e.message);
        default:
            rethrow;
    }
}
```

```python
# Python
from appwrite.exception import AppwriteException

try:
    tables_db.create_row(...)
except AppwriteException as e:
    if e.code == 409:
        tables_db.update_row(...)
    elif e.code == 429:
        time.sleep(2)
    elif e.code == 404:
        raise RowNotFoundError(e.message)
    else:
        raise
```

```typescript
// TypeScript
try {
    await tablesDB.createRow({...});
} catch (e) {
    if (e.code === 409) {
        await tablesDB.updateRow({...});
    } else if (e.code === 429) {
        await new Promise(r => setTimeout(r, 2000));
    } else if (e.code === 404) {
        throw new RowNotFoundError(e.message);
    } else {
        throw e;
    }
}
```

---

## Timeout Handling

API timeout: 15s. Long ops may fail.

```dart
// Dart - Handle timeout
try {
    await tablesDB.listRows(...).timeout(Duration(seconds: 30));
} on TimeoutException {
    // Query too slow - add index or reduce result set
}
```

---

## Related

- Rate limits → limits info
- Performance → query optimization
