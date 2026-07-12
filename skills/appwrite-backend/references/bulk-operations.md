# Bulk Operations

## Contents

- Overview
- Bulk Create
- Bulk Update
- Bulk Delete
- Limits
- Error Handling
- Performance Tips
- Common Patterns
- When to Use What
- Related

## Overview

Bulk API process many rows per request. Use for mass import/update/delete.

**Key diff from Transactions:**
- Transactions: all-or-nothing atomic
- Bulk: independent ops, partial success OK

---

## Bulk Create

```dart
final rows = await tablesDB.bulkCreateRows(
    databaseId: 'db', tableId: 'products',
    rows: [
        {'name': 'Product A', 'price': 29.99, 'stock': 100},
        {'name': 'Product B', 'price': 49.99, 'stock': 50},
    ],
);
```

```python
rows = tables_db.bulk_create_rows(
    database_id='db', table_id='products',
    rows=[
        {'name': 'Product A', 'price': 29.99, 'stock': 100},
        {'name': 'Product B', 'price': 49.99, 'stock': 50},
    ],
)
```

```typescript
const rows = await tablesDB.bulkCreateRows({
    databaseId: 'db', tableId: 'products',
    rows: [
        { name: 'Product A', price: 29.99, stock: 100 },
        { name: 'Product B', price: 49.99, stock: 50 },
    ],
});
```

---

## Bulk Update

### Same Data

```dart
await tablesDB.bulkUpdateRows(
    databaseId: 'db', tableId: 'products',
    rowIds: ['prod_1', 'prod_2', 'prod_3'],
    data: {'status': 'active'},
);
```

### Different Data

```dart
await tablesDB.bulkUpdateRows(
    databaseId: 'db', tableId: 'products',
    rows: [
        {'$id': 'prod_1', 'price': 24.99},
        {'$id': 'prod_2', 'price': 44.99},
    ],
);
```

### With Operators

```dart
await tablesDB.bulkUpdateRows(
    databaseId: 'db', tableId: 'products',
    rowIds: ['prod_1', 'prod_2'],
    data: {'stock': Operator.increment(10)},
);
```

---

## Bulk Delete

```dart
await tablesDB.bulkDeleteRows(
    databaseId: 'db', tableId: 'products',
    rowIds: ['prod_1', 'prod_2', 'prod_3'],
);
```

---

## Limits

Max rows per bulk create/update/delete: **1000**.

---

## Error Handling

Bulk ops return partial results on failure.

```dart
try {
    final result = await tablesDB.bulkCreateRows(
        databaseId: 'db', tableId: 'products', rows: products);
    for (final row in result.rows) {
        if (row.error != null) print('Failed: ${row.error}');
    }
} on AppwriteException catch (e) {
    print('Bulk operation failed: ${e.message}');
}
```

---

## Performance Tips

1. **Batch 500-row chunks** — under limit, balance latency
2. **Independent ops only** — no row deps
3. **Transactions for related data** — when atomic matters

---

## Common Patterns

### Import from CSV

```dart
Future<void> importProducts(String csvPath) async {
    final lines = await File(csvPath).readAsLines();
    final headers = lines.first.split(',');
    final rows = lines.skip(1).map((line) {
        final values = line.split(',');
        return Map.fromIterables(headers, values);
    }).toList();

    for (var i = 0; i < rows.length; i += 500) {
        final batch = rows.skip(i).take(500).toList();
        await tablesDB.bulkCreateRows(
            databaseId: 'db', tableId: 'products', rows: batch);
    }
}
```

### Mass Status Update

```dart
final oldOrders = await tablesDB.listRows(
    databaseId: 'db', tableId: 'orders',
    queries: [
        Query.lessThan('$createdAt', archiveDate),
        Query.equal('status', 'completed'),
        Query.select(['\$id']),
        Query.limit(1000),
    ],
    total: false,
);

await tablesDB.bulkUpdateRows(
    databaseId: 'db', tableId: 'orders',
    rowIds: oldOrders.rows.map((r) => r['\$id']).toList(),
    data: {'status': 'archived'},
);
```

### Cleanup Expired

```dart
final expired = await tablesDB.listRows(
    databaseId: 'db', tableId: 'sessions',
    queries: [
        Query.lessThan('expiresAt', DateTime.now().toIso8601String()),
        Query.select(['\$id']),
        Query.limit(1000),
    ],
    total: false,
);

await tablesDB.bulkDeleteRows(
    databaseId: 'db', tableId: 'sessions',
    rowIds: expired.rows.map((r) => r['\$id']).toList(),
);
```

---

## When to Use What

| Scenario | Use |
|----------|-----|
| Independent mass import | Bulk create |
| Update many with same value | Bulk update |
| Delete many by ID | Bulk delete |
| Related records must exist together | Transaction |
| All-or-nothing required | Transaction |
| Partial success acceptable | Bulk |

---

## Related

- [chunked-queries.md](chunked-queries.md) — chunked ID queries for big lists
- Transactions for atomic ops
- Operators for atomic field updates