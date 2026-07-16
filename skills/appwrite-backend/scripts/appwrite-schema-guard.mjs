#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PAGE_SIZE = 100;
const MAX_INVENTORY_AGE_MS = 15 * 60 * 1000;
const MAX_CLOCK_SKEW_MS = 5 * 60 * 1000;

function fail(message) {
  throw new Error(message);
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`invalid JSON ${path}: ${error.message}`);
  }
}

function inside(root, child) {
  const path = relative(root, child);
  return path !== "" && !path.startsWith("..") && !isAbsolute(path);
}

export function loadManifest(path) {
  const configPath = realpathSync(path);
  const rootDir = dirname(configPath);
  const config = readJson(configPath);
  const includes = config.includes ?? {};
  if (!includes || Array.isArray(includes) || typeof includes !== "object") {
    fail("config includes must be an object");
  }

  for (const key of ["tablesDB", "tables"]) {
    if (config[key] !== undefined && includes[key] !== undefined) {
      fail(`${key} cannot be inline and included`);
    }
    if (includes[key] !== undefined) {
      if (typeof includes[key] !== "string" || !includes[key].endsWith(".json")) {
        fail(`${key} include must be one JSON file`);
      }
      const includedPath = resolve(rootDir, includes[key]);
      if (!inside(rootDir, includedPath)) fail(`${key} include escapes project`);
      const value = readJson(includedPath);
      if (!Array.isArray(value)) fail(`${key} include must contain an array`);
      config[key] = value;
    }
  }

  if (typeof config.projectId !== "string" || config.projectId === "") {
    fail("config projectId is required");
  }
  if (typeof config.endpoint !== "string" || config.endpoint === "") {
    fail("config endpoint is required for target binding");
  }
  if (!Array.isArray(config.tablesDB) || !Array.isArray(config.tables)) {
    fail("complete tablesDB and tables arrays are required");
  }
  return config;
}

function identities(document, label) {
  const databases = new Set();
  const tables = new Set();
  for (const database of document.tablesDB ?? []) {
    if (!database || typeof database.$id !== "string" || database.$id === "") {
      fail(`${label} database lacks $id`);
    }
    if (databases.has(database.$id)) fail(`${label} duplicate database ${database.$id}`);
    databases.add(database.$id);
  }
  for (const table of document.tables ?? []) {
    if (!table || typeof table.$id !== "string" || typeof table.databaseId !== "string") {
      fail(`${label} table lacks databaseId/$id`);
    }
    if (!databases.has(table.databaseId)) {
      fail(`${label} table ${table.$id} references missing database ${table.databaseId}`);
    }
    const id = `${table.databaseId}/${table.$id}`;
    if (tables.has(id)) fail(`${label} duplicate table ${id}`);
    tables.add(id);
  }
  return { databases, tables };
}

export function checkManifest(config, inventory, baseline, now = Date.now()) {
  if (inventory.projectId !== config.projectId) fail("inventory project mismatch");
  if (inventory.endpoint !== config.endpoint) fail("inventory endpoint mismatch");
  const capturedAt = Date.parse(inventory.capturedAt);
  if (!Number.isFinite(capturedAt)) fail("inventory capturedAt is required");
  if (capturedAt > now + MAX_CLOCK_SKEW_MS) fail("inventory capturedAt is in the future");
  if (now - capturedAt > MAX_INVENTORY_AGE_MS) fail("inventory is stale");
  const candidate = identities(config, "candidate");
  const required = [identities(inventory, "inventory")];
  if (baseline) {
    if (baseline.projectId !== config.projectId) fail("baseline project mismatch");
    required.push(identities(baseline, "baseline"));
  }
  const missing = [];
  for (const source of required) {
    for (const id of source.databases) if (!candidate.databases.has(id)) missing.push(`database:${id}`);
    for (const id of source.tables) if (!candidate.tables.has(id)) missing.push(`table:${id}`);
  }
  if (missing.length > 0) fail(`manifest omits required resources: ${[...new Set(missing)].sort().join(", ")}`);
  return { result: "PASS", databases: candidate.databases.size, tables: candidate.tables.size };
}

function runCli(executable, args) {
  const output = execFileSync(executable, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  try {
    return JSON.parse(output);
  } catch (error) {
    fail(`Appwrite CLI returned non-JSON for ${args.join(" ")}: ${error.message}`);
  }
}

function debugEndpoint(executable) {
  const output = execFileSync(executable, ["client", "--debug"], { encoding: "utf8" });
  return output.match(/^endpoint\s+(.+)$/m)?.[1]?.trim();
}

function paged(executable, command, key) {
  const all = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const page = runCli(executable, ["--json", ...command, "--limit", String(PAGE_SIZE), "--offset", String(offset)]);
    if (!Array.isArray(page[key])) fail(`Appwrite response lacks ${key} array`);
    all.push(...page[key]);
    if (page[key].length === 0 || page[key].length < PAGE_SIZE || all.length >= Number(page.total)) break;
  }
  return all;
}

export function captureInventory(config, executable = "appwrite") {
  const endpoint = debugEndpoint(executable);
  if (endpoint !== config.endpoint) fail(`active endpoint mismatch: expected ${config.endpoint}; got ${endpoint ?? "unknown"}`);
  const project = runCli(executable, ["--json", "project", "get"]);
  if (project.$id !== config.projectId) fail("active project mismatch");
  const databases = paged(executable, ["tables-db", "list"], "databases");
  const tables = databases.flatMap((database) =>
    paged(executable, ["tables-db", "list-tables", "--database-id", database.$id], "tables")
      .map((table) => ({ $id: table.$id, databaseId: database.$id })),
  );
  return {
    schemaVersion: 1,
    capturedAt: new Date().toISOString(),
    endpoint: config.endpoint,
    projectId: config.projectId,
    tablesDB: databases.map((database) => ({ $id: database.$id })),
    tables,
  };
}

function argsMap(values) {
  const parsed = { command: values[0] };
  for (let index = 1; index < values.length; index += 2) parsed[values[index].replace(/^--/, "")] = values[index + 1];
  return parsed;
}

function main(values) {
  const args = argsMap(values);
  if (args.command === "capture") {
    if (!args.config || !args.output) fail("capture requires --config and --output");
    const inventory = captureInventory(loadManifest(args.config), args.appwrite ?? "appwrite");
    writeFileSync(args.output, `${JSON.stringify(inventory, null, 2)}\n`, { mode: 0o600 });
    console.log(JSON.stringify({ result: "PASS", output: args.output }));
    return;
  }
  if (args.command === "check") {
    if (!args.config || !args.inventory) fail("check requires --config and --inventory");
    const config = loadManifest(args.config);
    const baseline = args.baseline ? loadManifest(args.baseline) : undefined;
    console.log(JSON.stringify(checkManifest(config, readJson(args.inventory), baseline)));
    return;
  }
  fail("usage: appwrite-schema-guard.mjs capture|check ...");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === realpathSync(process.argv[1])) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(JSON.stringify({ result: "FAIL", error: error.message }));
    process.exitCode = 1;
  }
}
