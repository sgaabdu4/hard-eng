# Permissions and Roles

## Contents

- Overview
- Default Deny + Inheritance
- Actions
- Common Patterns
- Resource-Level Examples
- Common Mistakes
- Storage Note
- Related

## Overview

Use `Permission` + `Role` helpers. `write` grants `create + update + delete`.

---

## Default Deny + Inheritance

No user access unless perms set on row/file or inherited from table/bucket.

Use row/file perms when access differs per resource.
If all resources share same rules, set perms on table/bucket and leave row/file perms empty.

---

## Actions

| Action | Meaning |
|--------|---------|
| `read` | View resource |
| `create` | Create resource |
| `update` | Modify resource |
| `delete` | Remove resource |
| `write` | `create + update + delete` |

---

## Common Patterns

```dart
permissions: [
    Permission.read(Role.any()),
    Permission.create(Role.users()),
    Permission.update(Role.user(userId)),
    Permission.delete(Role.team('team_123', 'admin')),
    Permission.read(Role.label('premium')),
]
```

```python
permissions = [
    Permission.read(Role.any()),
    Permission.create(Role.users()),
    Permission.update(Role.user(user_id)),
    Permission.delete(Role.team('team_123', 'admin')),
    Permission.read(Role.label('premium')),
]
```

```typescript
permissions: [
    Permission.read(Role.any()),
    Permission.create(Role.users()),
    Permission.update(Role.user(userId)),
    Permission.delete(Role.team('team_123', 'admin')),
    Permission.read(Role.label('premium')),
]
```

---

## Resource-Level Examples

Set row/file-level permissions only when ACL differs per resource.

```typescript
await tablesDB.createRow({
    databaseId: 'db',
    tableId: 'posts',
    rowId: ID.unique(),
    data: {title: 'Hello'},
    permissions: [
        Permission.read(Role.user(userId)),
        Permission.update(Role.user(userId)),
        Permission.read(Role.team(teamId)),
    ],
});

await storage.createFile({
    bucketId: 'docs',
    fileId: ID.unique(),
    file,
    permissions: [
        Permission.read(Role.any()),
        Permission.update(Role.user(userId)),
        Permission.delete(Role.user(userId)),
    ],
});
```

If every row/file shares the same rules, set table/bucket permissions and leave
row/file permissions empty.

---

## Common Mistakes

- Forgetting perms. Resource becomes inaccessible to all users, including creator.
- `Role.any()` with `write`/`update`/`delete`. Guests can mutate or delete.
- `Permission.read(Role.any())` on sensitive rows/files. Data becomes public.
- Repeating row/file perms everywhere when table/bucket perms already fit. Harder ACL maintenance.

---

## Storage Note

File-level perms need `fileSecurity: true` on bucket. Otherwise bucket perms apply to all files.

---

## Related

- [storage-files.md](storage-files.md)
- [teams.md](teams.md)
- [authentication.md](authentication.md)
