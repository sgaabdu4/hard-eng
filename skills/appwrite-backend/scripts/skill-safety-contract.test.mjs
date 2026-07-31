import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const text = (path) => readFile(new URL(path, root), "utf8");

test("every Appwrite CLI path routes to the CLI safety owner before action", async () => {
  const [skill, cli] = await Promise.all([
    text("SKILL.md"),
    text("references/appwrite-cli.md"),
  ]);
  assert.match(
    skill,
    /Any Appwrite CLI\/wrapper command[\s\S]*appwrite-cli\.md/u,
  );
  assert.match(cli, /Load this reference before any Appwrite CLI\/wrapper command/u);
  assert.match(cli, /inspect exact pinned command help/u);
  assert.match(cli, /unknown flags can execute a default deployment path/u);
  assert.match(cli, /Init\/pull\/push\/deploy\/generate[\s\S]*pinned CLI\/wrapper/u);
  assert.match(cli, /Durable automation, exact response fields, pagination\/retry[\s\S]*official Server SDK/u);
  assert.match(cli, /CLI presentation omits\/transforms a required field[\s\S]*official Server SDK; raw HTTP forbidden/u);
  assert.match(cli, /Do not alternate CLI\/SDK variants after a\s+failure/u);
  assert.match(skill, /before installing, binding,[\s\S]*probing, diagnosing, or mutating/u);
  assert.match(cli, /script PASS alone ≠ production gate PASS/u);
});

test("each Appwrite CLI caller preserves immutable committed config bytes", async () => {
  const cli = await text("references/appwrite-cli.md");
  const steps = [
    "require the full tracked checkout clean",
    "Before its first CLI invocation",
    "Fail before invoking the CLI",
    "Run every CLI invocation for that caller",
    "On success or failure, restore every protected file byte-for-byte",
    "Verify the full tracked checkout equals the committed revision",
    "Remove the caller-owned snapshot",
  ];
  let previous = -1;
  for (const step of steps) {
    const current = cli.indexOf(step);
    assert.ok(current > previous, `missing or out-of-order CLI integrity step: ${step}`);
    previous = current;
  }
  assert.match(cli, /`appwrite\.config\.json` \+ every tracked[\s\S]*named by `includes`/u);
  assert.match(cli, /dirty input is not an acceptable snapshot/u);
  assert.match(cli, /Fresh job\/caller = fresh capture before its first CLI invocation/u);
  assert.match(cli, /One earlier job's snapshot or restore[\s\S]*never covers a later[\s\S]*finalizer/u);
  assert.match(cli, /Newline-only repair, parsed-JSON equivalence, formatting normalization/u);
  assert.match(cli, /checking only[\s\S]*`appwrite\.config\.json` is insufficient/u);
});

test("CLI version, exact output, and API-key safety contracts stay explicit", async () => {
  const [cli, selfHosting] = await Promise.all([
    text("references/appwrite-cli.md"),
    text("references/self-hosting.md"),
  ]);
  assert.match(selfHosting, /Appwrite 1\.9\.6[\s\S]*`appwrite-cli` \| `23\.0\.0`/u);
  assert.match(cli, /npm install -g appwrite-cli@25\.0\.0/u);
  assert.match(cli, /Registry latest on 2026-07-31 = CLI\s+`25\.0\.0`/u);
  assert.match(cli, /Never float automation/u);
  assert.match(cli, /`--json`\/`-j` = filtered presentation[\s\S]*drops null\/blank values and nested object\/array fields/u);
  assert.match(cli, /omitted field ≠ empty\/missing server value/u);
  assert.match(cli, /exact field evidence \(`labels`, `\$permissions`, preferences, status, nested arrays\) = `--raw`\/`-R`/u);
  assert.match(cli, /whole-response parse \+ required-field presence assertion/u);
  assert.match(cli, /filtered JSON = `-j`[\s\S]*full redacted response = `-R`[\s\S]*`-J` is unsupported/u);
  assert.match(cli, /key-management caller = `keys\.read` \+ `keys\.write`/u);
  assert.match(cli, /configured API key wins over any saved cookie\/account session/u);
  assert.match(cli, /scope union must come from every real consumer call/u);
  assert.match(cli, /enumerate exact consumer variable \+ secret-store names first/u);
  assert.match(cli, /create the first key in the Appwrite Console/u);
  assert.match(cli, /one bounded non-logging process/u);
  assert.match(cli, /Probe the actual consumer with the candidate key/u);
  assert.match(cli, /metadata output never proves the actual consumer received the secret/u);
});

test("release-matched SDK pins require call-shape migration proof", async () => {
  const [skill, selfHosting] = await Promise.all([
    text("SKILL.md"),
    text("references/self-hosting.md"),
  ]);
  assert.match(skill, /Compatible with `1\.9\.x`[^\n]*does not mean release-matched/u);
  assert.match(skill, /audit every intervening breaking change/u);
  assert.match(skill, /real SDK calls against the candidate/u);
  assert.match(selfHosting, /Python `16\.0\.0\+`[^\n]*typed Pydantic models/u);
  assert.match(selfHosting, /requirements-only upgrade leaves `result\["total"\]` \+/u);
  assert.match(selfHosting, /exact isolated dependency resolution/u);
});

test("numeric schema distinguishes 32-bit integer from 64-bit bigint", async () => {
  const schema = await text("references/schema-management.md");
  assert.match(schema, /`integer` \| signed 32-bit/u);
  assert.match(schema, /`bigint` \| signed 64-bit/u);
  assert.match(schema, /Number\.isSafeInteger/u);
});

test("retryable creates preallocate and reuse an SDK resource ID", async () => {
  const skill = await text("SKILL.md");
  assert.match(skill, /call `ID\.unique\(\)` before the first attempt/u);
  assert.match(skill, /persist the returned ID in the durable draft\/intent/u);
  assert.match(skill, /reuse that exact ID for every retry\/reconciliation/u);
  assert.match(skill, /identity remains in indexed columns/u);
  assert.match(skill, /never derive resource IDs/u);
});

test("SDK routing lives in the always-loaded router", async () => {
  const skill = await text("SKILL.md");
  assert.match(skill, /`node-appwrite`/u);
  assert.match(skill, /`dart_appwrite`/u);
  assert.match(skill, /https:\/\/<REGION>\.cloud\.appwrite\.io\/v1/u);
  assert.match(skill, /CLI account login endpoint stays/u);
  assert.doesNotMatch(skill, /React Native|react-native/iu);
});

test("production migration contract preserves data and exact ACL proof", async () => {
  const migration = await text("references/production-migrations.md");
  assert.match(
    migration,
    /bind → preflight → expand → backfill → verify → deploy-compatible → contract → activate → final read-back/u,
  );
  assert.match(migration, /Missing `\$permissions`[\s\S]*never `\[\]`/u);
  assert.match(migration, /row writes do not invalidate cached lists/u);
  assert.match(migration, /rollback-by-deletion requires separate destructive proof\/approval/u);
  assert.match(migration, /secret status = one-way/iu);
});

test("transaction and recovery owners cover recurring production failures", async () => {
  const [transactions, recovery] = await Promise.all([
    text("references/transactions.md"),
    text("references/self-hosting-ops.md"),
  ]);
  assert.match(transactions, /same `transactionId`/u);
  assert.match(transactions, /schema \+ Auth \+ Storage \+ Functions/u);
  assert.match(transactions, /One bulk row call with `transactionId` = one operation/u);
  assert.match(transactions, /Multiple committed chunks are not globally atomic/u);
  assert.match(transactions, /secondary failure replaces, rethrows over, or erases the primary failure/u);
  assert.match(transactions, /`primaryError` \+ `recoveryError` \+ their stack traces/u);
  assert.match(transactions, /preserves the primary as the top-level operation failure/u);
  assert.match(recovery, /isolated Appwrite\/database clone/u);
  assert.match(recovery, /metadata\/registry \+ database \+ Storage \+ config \+ cache/u);
  assert.match(recovery, /SQL counts alone = incomplete/u);
});

test("bulk owner matches current Appwrite atomicity and budgeting contracts", async () => {
  const [skill, bulk, limits] = await Promise.all([
    text("SKILL.md"),
    text("references/bulk-operations.md"),
    text("references/limits.md"),
  ]);
  assert.match(skill, /Preserve write intent before optimizing/u);
  assert.match(skill, /update-only work never routes through `upsertRow`\/`upsertRows`/u);
  assert.match(skill, /pre-read, existence check, or full payload/u);
  assert.match(skill, /heterogeneous per-row updates → `createOperations` with `action: update`/u);
  assert.match(bulk, /server SDK only/u);
  assert.match(bulk, /one bulk request is all-or-nothing/u);
  assert.match(bulk, /`createRows` \+ `updateRows` \+ `upsertRows` \+ `deleteRows`/u);
  assert.match(bulk, /`deleteRows` → N `deleteRow` calls changes one atomic request into N operations/u);
  assert.match(bulk, /pass its `transactionId` to every `deleteRow` \+ commit explicitly/u);
  assert.match(bulk, /one transaction operation per `deleteRow`/u);
  assert.match(bulk, /silently accepting partial deletion = forbidden/u);
  assert.match(bulk, /injected late delete failure must leave every target row unchanged/u);
  assert.match(bulk, /Domain\/adapter `update` → Appwrite `update`/u);
  assert.match(bulk, /Forbidden = `update` mapped to `upsertRow`\/`upsertRows`/u);
  assert.match(bulk, /transaction state \+ delete\/rollback\/concurrency/u);
  assert.match(bulk, /Heterogeneous per-row data\/ACL → `createOperations`/u);
  assert.match(bulk, /Each top-level update entry consumes one transaction operation/u);
  assert.match(bulk, /never weaken update into upsert/u);
  assert.match(bulk, /Empty queries = all rows/u);
  assert.match(bulk, /without relationship columns/u);
  assert.match(bulk, /One bulk call with `transactionId` \| `1`/u);
  assert.match(bulk, /chunkSize = min\(deployedBulkRowLimit, deployedQueryEqualValueLimit\)/u);
  assert.match(bulk, /transactionOps = ceil\(targetRows \/ chunkSize\) \+ otherStagedOperations/u);
  assert.match(bulk, /first page avoids cursoring after a row/u);
  assert.match(bulk, /both `Query\.equal\('\$id', chunkIds\)` \+ the original source predicate/u);
  assert.match(bulk, /Multiple bulk requests\/chunks = not one atomic unit/u);
  assert.match(bulk, /exact source-owner count `0`/u);
  assert.doesNotMatch(bulk, /partial success OK/u);
  assert.match(limits, /Self-hosted `1\.9\.0` fallback/u);
  assert.match(limits, /Target source\/config wins/u);
  assert.doesNotMatch(`${skill}\n${bulk}\n${limits}`, /\b(?:Free|Pro|Scale)\b/u);
});

test("SKILL remains a bounded router", async () => {
  const skill = await text("SKILL.md");
  assert.ok(skill.split("\n").length <= 220);
  assert.match(skill, /production-migrations\.md/u);
});

test("every reference has exactly one router row and no orphans", async () => {
  const skill = await text("SKILL.md");
  const files = (await readdir(new URL("references/", root))).sort();
  const linked = [...skill.matchAll(/\(references\/([a-z0-9-]+\.md)\)/gu)].map(
    (m) => m[1],
  );
  assert.deepEqual(
    [...new Set(linked)].sort(),
    files,
    "SKILL.md must link every reference and only existing references",
  );
});

test("recurring production failure contracts stay with canonical owners", async () => {
  const [migration, transactions, performance, query] = await Promise.all([
    text("references/production-migrations.md"),
    text("references/transactions.md"),
    text("references/performance.md"),
    text("references/query-optimization.md"),
  ]);
  assert.match(migration, /explicit `null`/u);
  assert.match(migration, /execution `completed` = transport proof only/u);
  assert.match(migration, /real authenticated critical route/u);
  assert.match(transactions, /count every staged operation/u);
  assert.match(performance, /Dependency-Aware Bootstrap/u);
  assert.match(query, /appwrite-query-contract\.mjs/u);
});
