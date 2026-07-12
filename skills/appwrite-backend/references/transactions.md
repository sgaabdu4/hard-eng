# Transactions

## Contents

- Overview
- Transaction Patterns
- Operation Types
- Limits
- Common Patterns
- Error Handling
- When NOT to Use Transactions
- Related

## Overview

Transactions execute multiple database operations atomically. All succeed or all fail.

**Use transactions when:**
- Transferring between records (balance, inventory)
- Creating related records that must exist together
- Multi-step operations requiring full completion

---

## Transaction Patterns

### Dart

```dart
import 'package:dart_appwrite/dart_appwrite.dart';

final client = Client()
    .setEndpoint('https://cloud.appwrite.io/v1')
    .setProject('PROJECT_ID')
    .setKey('API_KEY');

final tablesDB = TablesDB(client);

// Transfer credits between users
Future<void> transferCredits(String fromId, String toId, int amount) async {
    await tablesDB.transaction(
        databaseId: 'main',
        operations: [
            TransactionUpdate(
                tableId: 'users',
                rowId: fromId,
                data: {
                    'credits': Operator.decrement(amount),
                },
            ),
            TransactionUpdate(
                tableId: 'users',
                rowId: toId,
                data: {
                    'credits': Operator.increment(amount),
                },
            ),
            TransactionCreate(
                tableId: 'transfers',
                data: {
                    'from': fromId,
                    'to': toId,
                    'amount': amount,
                    'timestamp': DateTime.now().toIso8601String(),
                },
            ),
        ],
    );
}
```

### Python

```python
from appwrite.client import Client
from appwrite.services.tables_db import TablesDB
from appwrite.transaction import TransactionUpdate, TransactionCreate
from appwrite.operator import Operator

client = Client()
client.set_endpoint('https://cloud.appwrite.io/v1')
client.set_project('PROJECT_ID')
client.set_key('API_KEY')

tables_db = TablesDB(client)

def transfer_credits(from_id: str, to_id: str, amount: int) -> None:
    """Transfer credits atomically."""
    tables_db.transaction(
        database_id='main',
        operations=[
            TransactionUpdate(
                table_id='users',
                row_id=from_id,
                data={
                    'credits': Operator.decrement(amount),
                },
            ),
            TransactionUpdate(
                table_id='users',
                row_id=to_id,
                data={
                    'credits': Operator.increment(amount),
                },
            ),
            TransactionCreate(
                table_id='transfers',
                data={
                    'from': from_id,
                    'to': to_id,
                    'amount': amount,
                },
            ),
        ],
    )
```

### TypeScript

```typescript
import { Client, TablesDB, TransactionUpdate, TransactionCreate, Operator } from 'node-appwrite';

const client = new Client()
    .setEndpoint('https://cloud.appwrite.io/v1')
    .setProject('PROJECT_ID')
    .setKey('API_KEY');

const tablesDB = new TablesDB(client);

async function transferCredits(fromId: string, toId: string, amount: number): Promise<void> {
    await tablesDB.transaction({
        databaseId: 'main',
        operations: [
            new TransactionUpdate({
                tableId: 'users',
                rowId: fromId,
                data: {
                    credits: Operator.decrement(amount),
                },
            }),
            new TransactionUpdate({
                tableId: 'users',
                rowId: toId,
                data: {
                    credits: Operator.increment(amount),
                },
            }),
            new TransactionCreate({
                tableId: 'transfers',
                data: {
                    from: fromId,
                    to: toId,
                    amount,
                    timestamp: new Date().toISOString(),
                },
            }),
        ],
    });
}
```

---

## Operation Types

| Type | Description |
|------|-------------|
| `TransactionCreate` | Insert new row |
| `TransactionUpdate` | Update existing row |
| `TransactionDelete` | Remove row |

---

## Limits

| Setting | Value |
|---------|-------|
| Max operations per transaction | 100 |
| Timeout | 30 seconds |
| Single database | Yes (all ops same DB) |

---

## Common Patterns

### Order with inventory decrement

```dart
await tablesDB.transaction(
    databaseId: 'store',
    operations: [
        TransactionUpdate(
            tableId: 'products',
            rowId: productId,
            data: {
                'stock': Operator.decrement(quantity),
            },
        ),
        TransactionCreate(
            tableId: 'orders',
            data: {
                'product': productId,
                'quantity': quantity,
                'user': userId,
                'status': 'pending',
            },
        ),
    ],
);
```

### User signup with profile

```dart
await tablesDB.transaction(
    databaseId: 'app',
    operations: [
        TransactionCreate(
            tableId: 'users',
            rowId: userId, // Use same ID
            data: {
                'email': email,
                'createdAt': DateTime.now().toIso8601String(),
            },
        ),
        TransactionCreate(
            tableId: 'profiles',
            data: {
                'user': userId,
                'displayName': name,
                'avatar': null,
            },
        ),
        TransactionCreate(
            tableId: 'settings',
            data: {
                'user': userId,
                'notifications': true,
                'theme': 'system',
            },
        ),
    ],
);
```

---

## Error Handling

Transactions fail completely on any error. Every error rolls back all operations.

```dart
try {
    await tablesDB.transaction(...);
} on AppwriteException catch (e) {
    if (e.code == 409) {
        // Conflict - row modified during transaction
        // Retry with fresh data
    }
    if (e.code == 404) {
        // Row not found
    }
    rethrow;
}
```

---

## When NOT to Use Transactions

**Avoid transactions for:**
- Independent operations (no relationship)
- Read operations (use Query batching)
- Cross-database operations (single-database only)
- Operations that can succeed independently

**Prefer operators for single-record mutations:**

```dart
// ❌ Transaction overkill for single update
await tablesDB.transaction(
    operations: [
        TransactionUpdate(tableId: 't', rowId: 'x', data: {'count': Operator.increment(1)}),
    ],
);

// ✅ Direct update with operator
await tablesDB.updateRow(
    databaseId: 'db',
    tableId: 't',
    rowId: 'x',
    data: {'count': Operator.increment(1)},
);
```

---

## Related

- Atomic operators for race-safe updates · Bulk API for independent mass operations
