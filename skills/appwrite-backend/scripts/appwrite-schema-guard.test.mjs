import assert from "node:assert/strict";
import { chmodSync, mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { captureInventory, checkManifest, loadManifest } from "./appwrite-schema-guard.mjs";

const endpoint = "https://example.invalid/v1";
const projectId = "project";
const now = Date.parse("2026-07-16T00:10:00.000Z");

function manifest(databases = ["primary"], tables = [["primary", "users"]]) {
  return {
    capturedAt: "2026-07-16T00:00:00.000Z",
    endpoint,
    projectId,
    tablesDB: databases.map(($id) => ({ $id })),
    tables: tables.map(([databaseId, $id]) => ({ databaseId, $id })),
  };
}

test("complete manifest passes live and baseline inventory", () => {
  const candidate = manifest(["primary"], [["primary", "users"], ["primary", "orders"]]);
  assert.equal(checkManifest(candidate, manifest(), manifest(), now).result, "PASS");
});

test("index over array column fails before Appwrite mutation", () => {
  const candidate = manifest();
  candidate.tables[0].columns = [
    { key: "labels", array: true },
    { key: "status", array: false },
  ];
  candidate.tables[0].indexes = [{ key: "labels_status", attributes: ["labels", "status"] }];
  assert.throws(
    () => checkManifest(candidate, manifest(), undefined, now),
    /index primary\/users\/labels_status uses array column: labels/,
  );
});

test("scalar index remains valid", () => {
  const candidate = manifest();
  candidate.tables[0].columns = [{ key: "status", array: false }];
  candidate.tables[0].indexes = [{ key: "status_idx", attributes: ["status"] }];
  assert.equal(checkManifest(candidate, manifest(), undefined, now).result, "PASS");
});

test("narrowed manifest cannot omit a live database", () => {
  assert.throws(
    () => checkManifest(manifest([], []), manifest(), undefined, now),
    /database:primary/,
  );
});

test("narrowed manifest cannot omit a live table", () => {
  assert.throws(
    () => checkManifest(manifest(["primary"], []), manifest(), undefined, now),
    /table:primary\/users/,
  );
});

test("baseline prevents deletion hidden by a stale live capture", () => {
  assert.throws(
    () => checkManifest(manifest(["primary"], []), manifest(["primary"], []), manifest(), now),
    /table:primary\/users/,
  );
});

test("inventory target mismatch fails closed", () => {
  assert.throws(
    () => checkManifest(manifest(), { ...manifest(), projectId: "wrong" }, undefined, now),
    /project mismatch/,
  );
});

test("duplicate identities fail closed", () => {
  const candidate = manifest(["primary", "primary"], []);
  assert.throws(() => checkManifest(candidate, manifest(), undefined, now), /duplicate database/);
});

test("orphan table fails closed", () => {
  const candidate = manifest(["primary"], [["missing", "users"]]);
  assert.throws(() => checkManifest(candidate, manifest(), undefined, now), /references missing database/);
});

test("stale inventory fails closed", () => {
  const inventory = { ...manifest(), capturedAt: "2026-07-15T23:00:00.000Z" };
  assert.throws(() => checkManifest(manifest(), inventory, undefined, now), /stale/);
});

test("includes resolve only arrays inside project", () => {
  const root = mkdtempSync(join(tmpdir(), "appwrite-schema-guard-"));
  mkdirSync(join(root, "appwrite"));
  writeFileSync(join(root, "appwrite", "databases.json"), '[{"$id":"primary"}]');
  writeFileSync(join(root, "appwrite", "tables.json"), '[{"$id":"users","databaseId":"primary"}]');
  writeFileSync(join(root, "appwrite.config.json"), JSON.stringify({
    endpoint,
    projectId,
    includes: {
      tablesDB: "appwrite/databases.json",
      tables: "appwrite/tables.json",
    },
  }));
  const loaded = loadManifest(join(root, "appwrite.config.json"));
  assert.equal(loaded.tablesDB[0].$id, "primary");
  assert.equal(loaded.tables[0].$id, "users");
});

test("missing include fails closed", () => {
  const root = mkdtempSync(join(tmpdir(), "appwrite-schema-guard-"));
  writeFileSync(join(root, "appwrite.config.json"), JSON.stringify({
    endpoint,
    projectId,
    includes: { tablesDB: "missing.json" },
    tables: [],
  }));
  assert.throws(() => loadManifest(join(root, "appwrite.config.json")), /invalid JSON/);
});

test("capture uses read-only project and paginated inventory commands", () => {
  const root = mkdtempSync(join(tmpdir(), "appwrite-schema-guard-"));
  const executable = join(root, "appwrite");
  writeFileSync(executable, `#!/usr/bin/env node
const args = process.argv.slice(2).join(" ");
if (args === "client --debug") process.stdout.write("endpoint     ${endpoint}\\n");
else if (args === "--json project get") process.stdout.write(JSON.stringify({$id:"${projectId}"}));
else if (args.startsWith("--json tables-db list-tables")) process.stdout.write(JSON.stringify({total:1,tables:[{$id:"users"}]}));
else if (args.startsWith("--json tables-db list")) process.stdout.write(JSON.stringify({total:1,databases:[{$id:"primary"}]}));
else process.exit(2);
`);
  chmodSync(executable, 0o700);
  const inventory = captureInventory(manifest(), executable);
  assert.deepEqual(inventory.tablesDB, [{ $id: "primary" }]);
  assert.deepEqual(inventory.tables, [{ $id: "users", databaseId: "primary" }]);
});
