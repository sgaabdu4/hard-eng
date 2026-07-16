# Appwrite CLI

Load this reference before any Appwrite CLI/wrapper command, deployment, schema
sync, function-variable operation, or CLI troubleshooting. Do not probe first.

## Route

- Read/query only → bind target → exact command
- Function code deployment → function-only command
- Schema/resource reconciliation → Safety Gate → scoped push
- Data/ACL migration → [production-migrations.md](production-migrations.md) → SDK-first bounded runner
- Production schema push → inventory + backup/recovery + approval
- Destructive intent → dedicated delete command + exact resource approval
- CLI/wrapper failure → version + help/source + sanitized response shape → owner diagnosis

## Binding

```shell
appwrite --version
appwrite client \
  --endpoint "$APPWRITE_ENDPOINT" \
  --project-id "$APPWRITE_PROJECT_ID" \
  --key "$APPWRITE_API_KEY"
appwrite client --debug
appwrite --json project get
```

Required:

- endpoint = intended environment
- returned `$id` = intended project
- key = masked; `--show-secrets` forbidden
- mismatch/unknown → stop
- global reset → `appwrite client --reset`

Before command construction:

- repository-pinned binary/wrapper + version = authority; generic skill pin never overrides it
- inspect exact pinned command help: `appwrite <service> <command> --help`
- repository wrapper help is allowed only when its dispatcher explicitly owns help; unknown flags can execute a default deployment path
- classify command as read-only, additive, reconcile, data mutation, or delete
- no troubleshooting/mutation until target + version + command shape are known

Secret safety:

- `set -x`, shell trace, process-list diagnostics, verbose credential commands = forbidden
- bind with short-lived least-scope key + protected environment; capture only masked debug output
- unexpected secret in output/process evidence → stop command → revoke/rotate → replace every consumer → resume from read-back

## Config

`appwrite.config.json` = complete desired-state manifest for every pushed type.

```json
{
  "projectId": "<PROJECT_ID>",
  "endpoint": "https://<ENDPOINT>/v1",
  "includes": {
    "functions": "appwrite/functions.json",
    "tablesDB": "appwrite/databases.json",
    "tables": "appwrite/tables.json"
  }
}
```

Include value = one relative JSON file containing one array. Glob/array/URL,
missing file, parent path, or inline + included duplicate owner → invalid.

## Command Shapes

- CLI option shapes vary by version → command help + official source before automation.
- Array options = variadic arguments, not one JSON-encoded array.

```shell
appwrite tables-db update-row \
  --database-id "<DATABASE_ID>" \
  --table-id "<TABLE_ID>" \
  --row-id "<ROW_ID>" \
  --permissions 'read("user:<USER_ID>")' 'update("user:<USER_ID>")'
```

- Omitted `--permissions` = inherit/preserve; explicit empty ACL = revoke all resource ACLs.
- Pinned CLI cannot encode `[]` → official Server SDK `permissions: []`; omission/skipping = forbidden.
- `ID.unique()` = SDK helper. CLI sentinel handling differs → verify pinned help/source; unsupported sentinel → create through official SDK and use returned ID.
- Required nullable-column contraction may need explicit JSON `null`; boolean/string stand-ins = forbidden.

## Init

```shell
appwrite init project
appwrite init functions
appwrite init tables
appwrite init buckets
appwrite init teams
appwrite init topics
```

Init = local manifest write. Existing project → preserve full manifest → init →
review diff → Schema Safety Gate before any push.

## Destructive Semantics

Official CLI behavior:

- `push tables` → remote database absent from `tablesDB` = delete database
- database deletion → all contained tables/data deleted
- remote table absent from `tables` = delete table
- `--force` → confirmation auto-accept
- `--all` → select every available resource
- no supported dry-run flag exists in CLI 22.4.0

Therefore:

- `appwrite push all` = production forbidden
- production `appwrite push tables --all --force` = forbidden
- narrowed/feature-only/schema-only manifest = forbidden push input
- warning text/interactive prompt = last defense, not proof
- schema deletion via omission = forbidden; use exact delete API/CLI command after
  backup + recovery proof + explicit approval

## Schema Safety Gate

Run before every production `push tables`:

```shell
node skills/appwrite-backend/scripts/appwrite-schema-guard.mjs capture \
  --config appwrite.config.json \
  --output /tmp/appwrite-live-inventory.json

node skills/appwrite-backend/scripts/appwrite-schema-guard.mjs check \
  --config appwrite.config.json \
  --inventory /tmp/appwrite-live-inventory.json \
  --baseline <BASELINE_APPWRITE_CONFIG>
```

`capture` = read-only database/table inventory; names/data/secrets excluded.

PASS requires:

- endpoint + project binding verified
- inventory age ≤15 minutes
- complete includes resolved
- no duplicate database/table identity
- every live database/table present locally
- every baseline database/table present locally
- recent backup/snapshot + tested recovery path recorded
- exact command + environment + revision approved

Any omitted/mismatched resource → FAIL; do not push.

Guard output proves binding/inventory/manifest completeness only. Backup,
recovery-test, command, environment, revision, and approval = separate operator
receipts; script PASS alone ≠ production gate PASS.

Backup evidence when server supports Appwrite Backups:

```shell
appwrite --json backups list-archives --limit 100 --offset 0
appwrite --json backups get-archive --archive-id "<ARCHIVE_ID>"
appwrite --json backups list-restorations --limit 100 --offset 0
appwrite --json backups get-restoration --restoration-id "<RESTORATION_ID>"
```

Archive existence ≠ recovery proof. Unsupported Backups API → verified
infrastructure/database snapshot + tested restore owner.

## Pull

```shell
appwrite pull functions
appwrite pull tables
appwrite pull buckets
appwrite pull teams
appwrite pull webhooks
appwrite pull topics
```

Pull may replace local manifest. Review diff + rerun Schema Safety Gate before
push. Pull is not a backup of row data.

## Scoped Push

```shell
appwrite push functions
appwrite push tables
appwrite push buckets
appwrite push teams
appwrite push webhooks
appwrite push topics
```

Rules:

- push one resource type only
- production tables → Schema Safety Gate PASS first
- `--force` only after the same gate; it suppresses all confirmations
- CI must run the gate before any non-interactive push
- failure after mutation → stop; inventory + recovery evidence; no blind retry

## Function Deployments

Function code-only intent → avoid schema/resource push.

```shell
appwrite functions create-deployment --function-id "<FUNCTION_ID>"
appwrite functions list-deployments --function-id "<FUNCTION_ID>"
appwrite functions get-deployment \
  --function-id "<FUNCTION_ID>" \
  --deployment-id "<DEPLOYMENT_ID>"
appwrite functions update-deployment \
  --function-id "<FUNCTION_ID>" \
  --deployment-id "<DEPLOYMENT_ID>"
```

Function config/variables change → review full functions manifest before
`push functions`. Secrets = environment/secret manager; never tracked config.

### Function Variables

1. Validate candidate values locally from secret/config owners; no value logging.
2. List active variables; normalize array or `{total, variables}` response.
3. Upsert exact manifest keys + secret flags before deployment.
4. Secret → non-secret = delete + recreate; secret status is one-way.
5. Read back exact key/ID/count + `secret` metadata; secret values are intentionally unrecoverable.
6. Deploy after variable mutation; variables take effect only on the next deployment.
7. Runtime smoke proves value availability; metadata read-back alone does not.

Commands:

```shell
appwrite --json functions list-variables --function-id "<FUNCTION_ID>"
appwrite functions create-variable --function-id "<FUNCTION_ID>" ...
appwrite functions update-variable --function-id "<FUNCTION_ID>" ...
appwrite functions delete-variable --function-id "<FUNCTION_ID>" --variable-id "<VARIABLE_ID>"
```

## Read-Only Inventory + Diagnosis

```shell
appwrite --json project get
appwrite --json tables-db list --limit 100 --offset 0
appwrite --json tables-db list-tables \
  --database-id "<DATABASE_ID>" --limit 100 --offset 0
appwrite --json tables-db get-table \
  --database-id "<DATABASE_ID>" --table-id "<TABLE_ID>"
appwrite --json tables-db list-rows \
  --database-id "<DATABASE_ID>" --table-id "<TABLE_ID>"
appwrite --json storage list-files --bucket-id "<BUCKET_ID>"
appwrite --json functions list-executions --function-id "<FUNCTION_ID>"
```

- pagination = bounded `--limit` + `--offset` until complete
- `--json` = filtered JSON; `--raw` only when exact response required
- `--verbose` = sanitized error triage only; credential-bearing invocation/output = forbidden
- row/file output may contain PII → bounded destination + redact before sharing
- missing `$permissions` in list/bulk rows = unknown; ACL proof → exact `get-row`/`get-file`
- row writes do not invalidate cached list responses; verification → `ttl: 0`, exact GET, or explicit table purge

## Diagnosis

1. Capture pinned binary/wrapper version + exact help without secrets.
2. Reproduce with smallest read-only or disposable command shape.
3. Separate wrapper dispatch, CLI serialization, server validation, transport, and application failure.
4. Inspect official CLI/SDK source for that exact tag; generic latest behavior = insufficient.
5. Add command-shape regression → use official SDK for an unsupported CLI shape.
6. Mutation may have started → inventory current state; never rerun from assumption.

Bounded transport route:

- `429|502|503|504` + idempotent operation → exponential backoff + jitter + one absolute deadline
- empty/non-JSON response = transport failure, never proof of missing resource
- unknown status after write → exact resource read-back before retry
- per-row CLI process in migration = N+1 failure mode → SDK/client pool + bounded chunks

## Explicit Deletes

```shell
appwrite tables-db delete-table \
  --database-id "<DATABASE_ID>" --table-id "<TABLE_ID>"
appwrite tables-db delete --database-id "<DATABASE_ID>"
```

Required before delete:

- exact endpoint/project/resource IDs
- dependency + data-retention review
- restorable backup/snapshot + recovery test
- explicit destructive approval
- post-delete inventory verification

## Generate

```shell
appwrite generate
appwrite types ./src/generated
```

Generate after accepted schema change/pull.

## Sources

- Commands: <https://appwrite.io/docs/tooling/command-line/commands>
- Installation/config includes: <https://appwrite.io/docs/tooling/command-line/installation>
- Tables CLI: <https://appwrite.io/docs/tooling/command-line/tables>
- Non-interactive flags: <https://appwrite.io/docs/tooling/command-line/non-interactive>
- CLI source (`push.ts`, `database-sync.ts`, `change-approval.ts`):
  <https://github.com/appwrite/sdk-for-cli/tree/master/lib/commands>
- Exact pinned CLI tag/source = command-shape owner; reverify after version change.

## Related

- [schema-management.md](schema-management.md)
- [functions-advanced.md](functions-advanced.md)
- [self-hosting-ops.md](self-hosting-ops.md)
