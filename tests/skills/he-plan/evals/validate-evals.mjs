#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const data = JSON.parse(fs.readFileSync(path.join(root, "evals.json"), "utf8"));
const errors = [];

if (data.skill_name !== "he-plan") errors.push("skill_name must be he-plan");
if (data.model !== "gpt-5.4-mini") errors.push("model must be gpt-5.4-mini");
if (!Array.isArray(data.evals) || data.evals.length < 1) errors.push("evals must contain at least one case");

for (const item of data.evals || []) {
  if (!Number.isInteger(item.id)) errors.push(`eval id ${item.id} must be integer`);
  for (const key of ["prompt", "expected_output"]) {
    if (typeof item[key] !== "string" || !item[key].trim()) errors.push(`eval ${item.id} ${key} missing`);
  }
  if (!Array.isArray(item.expectations) || item.expectations.length < 4) {
    errors.push(`eval ${item.id} needs at least four expectations`);
  }
  const text = JSON.stringify(item).toLowerCase();
  for (const term of ["grill me", "comments", "visibility", "delegate", "admin", "not ready"]) {
    if (!text.includes(term)) errors.push(`eval ${item.id} missing coverage term ${term}`);
  }
}

if (errors.length) {
  console.error("FAIL");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log("he-plan-evals: pass");
