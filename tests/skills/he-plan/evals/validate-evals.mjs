#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));

export function validateHePlanEvals(data) {
  const errors = [];
  const seenIds = new Set();
  const evals = Array.isArray(data?.evals) ? data.evals : [];

  if (data?.skill_name !== "he-plan") errors.push("skill_name must be he-plan");
  if (data?.model !== "gpt-5.6-luna") errors.push("model must be gpt-5.6-luna");
  if (!Array.isArray(data?.evals) || evals.length < 1) errors.push("evals must contain at least one case");

  for (const [index, item] of evals.entries()) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      errors.push(`eval #${index + 1} must be object`);
      continue;
    }
    const label = Number.isInteger(item.id) ? item.id : `#${index + 1}`;
    if (!Number.isInteger(item.id)) {
      errors.push(`eval id ${item.id} must be integer`);
    } else if (seenIds.has(item.id)) {
      errors.push(`eval id ${item.id} must be unique`);
    } else {
      seenIds.add(item.id);
    }
    for (const key of ["prompt", "expected_output"]) {
      if (typeof item[key] !== "string" || !item[key].trim()) errors.push(`eval ${label} ${key} missing`);
    }
    if (!Array.isArray(item.expectations) || item.expectations.length < 4) {
      errors.push(`eval ${label} needs at least four expectations`);
    }
    if (item.files !== undefined) {
      if (!Array.isArray(item.files)) {
        errors.push(`eval ${label} files must be array`);
      } else {
        for (const [fileIndex, file] of item.files.entries()) {
          const fileLabel = `eval ${label} files[${fileIndex}]`;
          if (!file || typeof file !== "object" || Array.isArray(file)) {
            errors.push(`${fileLabel} must be object`);
            continue;
          }
          if (typeof file.path !== "string" || !file.path.trim()) {
            errors.push(`${fileLabel}.path missing`);
          } else {
            const normalized = path.posix.normalize(file.path.replaceAll("\\", "/"));
            if (
              normalized === "." ||
              normalized === ".." ||
              normalized.startsWith("../") ||
              normalized.startsWith("/") ||
              /^[A-Za-z]:/.test(normalized)
            ) {
              errors.push(`${fileLabel}.path must stay inside eval target`);
            }
          }
          if (typeof file.content !== "string") errors.push(`${fileLabel}.content must be string`);
        }
      }
    }
  }

  const suiteText = JSON.stringify(evals).toLowerCase();
  for (const term of ["grill me", "comments", "visibility", "delegate", "admin", "not ready", "screenshots", "source-to-plan coverage", "structural validation", "contradiction"]) {
    if (!suiteText.includes(term)) errors.push(`eval suite missing coverage term ${term}`);
  }

  return errors;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const data = JSON.parse(fs.readFileSync(path.join(root, "evals.json"), "utf8"));
  const errors = validateHePlanEvals(data);
  const stageContract = fs.readFileSync(path.resolve(root, "../../../../skills/he-plan/references/stage-contract.md"), "utf8").replace(/\s+/g, " ");
  for (const required of [
    "question-premise preflight",
    "exact user answer or accepted UI review receipt",
    "state says no question, emit no question",
    "commentary does not count as UI presentation",
    "source-to-plan coverage",
    "SHA-256 digest",
    "every nonblank source span exactly once",
    "sourceCoverage.required: false",
    "artifact shape, not content completeness"
  ]) {
    if (!stageContract.includes(required)) errors.push(`stage contract missing: ${required}`);
  }

  if (errors.length) {
    console.error("FAIL");
    for (const error of errors) console.error(`- ${error}`);
    process.exit(1);
  }

  console.log("he-plan-evals: pass");
}
