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

## Install + Maintain

```shell
npm install -g appwrite-cli            # pinned line
brew install appwrite/appwrite/appwrite  # macOS tap
appwrite update                        # in-place, detected install method
appwrite update --manual               # print instructions only
appwrite completion install
```

Repository-pinned wrapper/version wins over any install shown here. `appwrite update` changes command shapes → reverify pinned help before the next mutation.

## Binding

```shell
appwrite --version
appwrite login                         # interactive account
appwrite login --endpoint "https://<SELF_HOSTED>/v1"
appwrite login --switch                # change active saved account
appwrite client \
  --endpoint "$APPWRITE_ENDPOINT" \
  --project-id "$APPWRITE_PROJECT_ID" \
  --key "$APPWRITE_API_KEY"
appwrite client --debug
appwrite --json project get
```

`appwrite whoami` reporting `https://cloud.appwrite.io/v1` is the expected Cloud account login endpoint. Do not rewrite it to a region. Only project config and project-scoped calls use `https://<REGION>.cloud.appwrite.io/v1`.

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
  "endpoint": "https://<REGION>.cloud.appwrite.io/v1",
  "includes": {
    "functions": "appwrite/functions.json",
    "sites": "appwrite/sites.json",
    "webhooks": "appwrite/webhooks.json",
    "tablesDB": "appwrite/databases.json",
    "tables": "appwrite/tables.json"
  },
  "settings": { "services": {}, "protocols": {}, "auth": {} }
}
```

Include value = one relative JSON file containing one array. Glob/array/URL,
missing file, parent path, or inline + included duplicate owner → invalid.
Included function/site `path` resolves relative to the include file directory.

Pushed resource types: `settings` · `tablesDB` · `tables` · `buckets` · `teams`
· `topics` · `functions` · `sites` · `webhooks`. Every type participates in
reconciliation; a manifest missing one type is not a safe push input.

Function/site config fields: `enabled` · `logging` · `runtime`/`framework` ·
`buildSpecification` · `runtimeSpecification` · `buildRuntime` ·
`deploymentRetention` · `scopes` (execution-key API scopes) · `events` ·
`schedule` · `timeout` · `entrypoint`/`startCommand` · `commands`/`installCommand`/`buildCommand`
· `outputDirectory` · `adapter` · `fallbackFile` · `ignore` (newline-separated,
additive to `.gitignore`) · `path`.

Table config fields include `rowSecurity` (per-row ACL enforcement),
`$permissions`, `columns`, `indexes`. Flipping `rowSecurity` changes effective
access for every existing row → treat as an ACL migration, not a schema tweak.

### Tracked Config Integrity

Pinned CLI commands can pull after a push + rewrite the full local manifest with
their serializer. Protected closure = `appwrite.config.json` + every tracked
JSON file named by `includes`.

Each independent CLI caller/job:

1. Check out the exact release revision → require the full tracked checkout clean.
2. Before its first CLI invocation, capture each protected file byte-for-byte
   from that committed revision into a caller-owned, create-only `0600` snapshot.
3. Fail before invoking the CLI when any working file differs from the committed
   bytes; dirty input is not an acceptable snapshot.
4. Run every CLI invocation for that caller.
5. On success or failure, restore every protected file byte-for-byte from the
   snapshot before any downstream step.
6. Verify the full tracked checkout equals the committed revision; checking only
   `appwrite.config.json` is insufficient.
7. Remove the caller-owned snapshot.

Fresh job/caller = fresh capture before its first CLI invocation + its own
restore/clean-check. One earlier job's snapshot or restore never covers a later
finalizer. Newline-only repair, parsed-JSON equivalence, formatting normalization,
and capture after the first CLI call = forbidden.

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
appwrite init sites
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
- `push settings` omission semantics vary by CLI version. Inspect pinned source
  before a partial settings push. CLI `24.1.0` submits only defined settings,
  although its change preview renders omitted remote fields as blank.
- `push functions`/`push sites` with `--with-variables` → key absent from `.env` = deleted variable
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
appwrite pull settings
appwrite pull functions
appwrite pull sites
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
appwrite push settings
appwrite push functions
appwrite push sites
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

## List Query Flags

Prefer flags over raw `--queries` JSON on any list command. Flags are validated
by the CLI; hand-built query JSON is not.

```shell
appwrite --json tables-db list-rows \
  --database-id "<DATABASE_ID>" --table-id "<TABLE_ID>" \
  --where 'status=active' --where 'score>=10' \
  --sort-asc 'name' \
  --select '$id' --select 'name' \
  --limit 25 --cursor-after "<ROW_ID>"
```

- `--where` operators: `=` `!=` `>` `>=` `<` `<=`; values parse as string,
  number, boolean, `null`, or JSON array.
- `--sort-asc` · `--sort-desc` · `--limit` · `--offset` · `--cursor-after` ·
  `--cursor-before` apply to list commands; repeated `--select` applies to
  row/document list + get.
- Cursor flags over `--offset` for large tables; same O(1) vs O(n) rule as the SDK.
- `--queries` remains for shapes flags cannot express; verify against pinned help.

## Local Run

```shell
appwrite run functions
appwrite run functions --with-variables   # fetch values from function settings
```

Local run reads live variable values → treat the shell as secret-bearing.

## Function + Site Deployments

Code-only intent → avoid schema/resource push.

```shell
appwrite functions create-deployment --function-id "<FUNCTION_ID>"
appwrite functions list-deployments --function-id "<FUNCTION_ID>"
appwrite functions get-deployment \
  --function-id "<FUNCTION_ID>" \
  --deployment-id "<DEPLOYMENT_ID>"
appwrite functions update-deployment \
  --function-id "<FUNCTION_ID>" \
  --deployment-id "<DEPLOYMENT_ID>"
appwrite sites list-deployments --site-id "<SITE_ID>"
appwrite sites update-site-deployment --site-id "<SITE_ID>" --deployment-id "<DEPLOYMENT_ID>"
appwrite sites update-deployment-status --site-id "<SITE_ID>" --deployment-id "<DEPLOYMENT_ID>"  # cancel build
```

Staged rollout — build without switching live traffic, activate as a separate
approved step:

```shell
appwrite push functions --function-id "<FUNCTION_ID>" --activate=false
appwrite push functions --function-id "<FUNCTION_ID>" --activate
```

Default push activates. Any cutover requiring backfill, contract, or consumer
ordering uses `--activate=false` first — see
[production-migrations.md](production-migrations.md).

Function config/variables change → review full functions manifest before
`push functions`. Secrets = environment/secret manager; never tracked config.

### Function + Site Variables

1. Validate candidate values locally from secret/config owners; no value logging.
2. List active variables; normalize array or `{total, variables}` response.
3. Upsert exact manifest keys + secret flags before deployment.
4. Secret → non-secret = delete + recreate; secret status is one-way.
5. Read back exact key/ID/count + `secret` metadata; secret values are intentionally unrecoverable.
6. Deploy after variable mutation; variables take effect only on the next deployment.
7. Runtime smoke proves value availability; metadata read-back alone does not.

Variables are never declared in `appwrite.config.json`. They live in a `.env`
inside the configured `path`, and sync only on explicit request:

```shell
appwrite push functions --function-id "<FUNCTION_ID>" --with-variables
appwrite push sites --site-id "<SITE_ID>" --with-variables
appwrite push functions --function-id "<FUNCTION_ID>"   # code only, saved vars untouched
```

`--with-variables` creates, replaces, and removes remote variables to match the
local `.env` exactly. A key absent from `.env` is deleted. Verify the `.env`
against the secret owner before every `--with-variables` push.

Commands:

```shell
appwrite --json functions list-variables --function-id "<FUNCTION_ID>"
appwrite functions create-variable --function-id "<FUNCTION_ID>" ...
appwrite functions update-variable --function-id "<FUNCTION_ID>" ...
appwrite functions delete-variable --function-id "<FUNCTION_ID>" --variable-id "<VARIABLE_ID>"
```

## Project Settings

Singular `project` service = current-bound project; no `--project-id`.

```shell
appwrite project update-service --service-id functions --enabled true
appwrite project update-protocol --protocol-id rest --enabled true
appwrite project list-o-auth-2-providers
appwrite project update-o-auth-2-git-hub --enabled true
appwrite project list-policies
appwrite project create-mock-phone --phone "+1<TEST_NUMBER>" --otp "<CODE>"
appwrite project create-ephemeral-key
```

- Service/protocol toggles remove an entire API surface project-wide → treat as
  destructive; inventory consumers first.
- `push settings` reconciles these from the manifest; a partial `settings` block
  disables what it omits.
- Ephemeral keys are short-lived and preferred over long-lived keys for one-off
  bounded automation. Mock phones are non-production test fixtures only.

### Nullable policy compatibility

CLI `24.1.0` + self-hosted Appwrite `1.9.6` cannot disable the user limit
through the direct command:

- `project update-user-limit-policy --total null` → CLI integer parser rejects
  `null`
- `project update-user-limit-policy --total 0` → server rejects numeric `0`;
  its endpoint accepts `1..5000 | null`
- `push settings` maps local `0 | null` to API `null`

Safe correction:

1. Read version + direct-command help/source + current `user-limit` policy.
2. Use an isolated minimal config containing only
   `settings.auth.security.limit: null`.
3. Prove pinned push source skips undefined settings + maps this value to
   `null`.
4. Run scoped `appwrite --force push settings`.
5. Read back `project get-policy --policy-id user-limit`; disabled = `total: 0`.

CLI success text without exact policy read-back = unknown. Different CLI/server
pairing → reverify both serializers before mutation.

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
appwrite generate --output ./src/generated
appwrite generate --language typescript
appwrite generate --appwrite-import-source node-appwrite --import-extension .js
```

Emits `types.ts` + `databases.ts` + `constants.ts` + `index.ts`. Regenerate after
every accepted schema change/pull; stale generated types compile against a schema
that no longer exists.

Generated client collapses IDs and query builders into typed calls:

```typescript
import { databases } from './generated/appwrite';

const customers = databases.use('main').use('customers');
const page = await customers.list({
    queries: (q) => [q.equal('status', 'active'), q.orderDesc('$createdAt'), q.limit(25)],
});
await customers.createMany([{ name: 'A' }, { name: 'B' }]);
```

`createMany` is the generated bulk path and carries the same atomic-per-request
contract as `createRows` — see [bulk-operations.md](bulk-operations.md).

## Sources

- Commands: <https://appwrite.io/docs/tooling/command-line/commands>
- Installation/config includes: <https://appwrite.io/docs/tooling/command-line/installation>
- Tables CLI: <https://appwrite.io/docs/tooling/command-line/tables>
- Non-interactive flags: <https://appwrite.io/docs/tooling/command-line/non-interactive>
- CLI source (`push.ts`, `database-sync.ts`, `change-approval.ts`):
  <https://github.com/appwrite/sdk-for-cli/tree/master/lib/commands>
- CLI 22.4.0 schema push/pull write-back:
  <https://github.com/appwrite/sdk-for-cli/blob/22.4.0/lib/commands/schema.ts>
- CLI 22.4.0 four-space config/include serialization:
  <https://github.com/appwrite/sdk-for-cli/blob/22.4.0/lib/config.ts>
- CLI 24.1.0 user-limit command parser:
  <https://github.com/appwrite/sdk-for-cli/blob/24.1.0/lib/commands/services/project.ts>
- CLI 24.1.0 nullable settings push:
  <https://github.com/appwrite/sdk-for-cli/blob/24.1.0/lib/commands/push.ts>
- Appwrite 1.9.6 user-limit endpoint:
  <https://github.com/appwrite/appwrite/blob/1.9.6/src/Appwrite/Platform/Modules/Project/Http/Project/Policies/UserLimit/Update.php>
- Exact pinned CLI tag/source = command-shape owner; reverify after version change.

## Related

- [schema-management.md](schema-management.md)
- [functions-advanced.md](functions-advanced.md)
- [self-hosting-ops.md](self-hosting-ops.md)
