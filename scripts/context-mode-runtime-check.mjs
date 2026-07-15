#!/usr/bin/env node
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const root = process.argv[2];
if (!root) throw new Error("context-mode package path required");
const module = await import(pathToFileURL(resolve(root, "build/db-base.js")));
const Database = module.loadDatabase();
const database = new Database(":memory:");
try {
  database.exec("CREATE VIRTUAL TABLE proof USING fts5(body)");
  database.prepare("INSERT INTO proof(body) VALUES (?)").run("hard eng runtime");
  const row = database.prepare("SELECT count(*) AS count FROM proof WHERE proof MATCH ?").get("runtime");
  if (Number(row?.count) !== 1) throw new Error("context-mode FTS5 query failed");
} finally {
  database.close();
}
