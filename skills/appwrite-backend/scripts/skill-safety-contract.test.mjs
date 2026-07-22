import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
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
  assert.match(skill, /before installing, binding,[\s\S]*probing, diagnosing, or mutating/u);
  assert.match(cli, /script PASS alone ≠ production gate PASS/u);
});

test("numeric schema distinguishes 32-bit integer from 64-bit bigint", async () => {
  const schema = await text("references/schema-management.md");
  assert.match(schema, /`integer` \| signed 32-bit/u);
  assert.match(schema, /`bigint` \| signed 64-bit/u);
  assert.match(schema, /Number\.isSafeInteger/u);
});

test("retryable creates preallocate and reuse an SDK resource ID", async () => {
  const [skill, routing] = await Promise.all([
    text("SKILL.md"),
    text("references/sdk-routing.md"),
  ]);
  assert.match(skill, /call `ID\.unique\(\)` before the first attempt/u);
  assert.match(skill, /persist the returned ID in the durable draft\/intent/u);
  assert.match(skill, /reuse that exact ID for every retry\/reconciliation/u);
  assert.match(skill, /business\/natural identity remains in indexed columns/u);
  assert.match(skill, /never derive resource IDs/u);
  assert.match(routing, /Critical Rule 4/u);
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
  assert.match(recovery, /isolated Appwrite\/database clone/u);
  assert.match(recovery, /metadata\/registry \+ database \+ Storage \+ config \+ cache/u);
  assert.match(recovery, /SQL counts alone = incomplete/u);
});

test("SKILL remains a bounded router", async () => {
  const skill = await text("SKILL.md");
  assert.ok(skill.split("\n").length <= 500);
  assert.match(skill, /production-migrations\.md/u);
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
