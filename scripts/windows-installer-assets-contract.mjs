#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDocument } from "yaml";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const ASSET_ROOT = path.join(ROOT, "skills/building-flutter-apps/assets");
const WORKFLOW = path.join(ASSET_ROOT, "windows-installer-workflow.yml");
const REMOTE_ACTION = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[0-9a-f]{40}$/u;
const OUTPUTS = ["mode", "revision", "event_sha", "version", "diagnostic_run_id"];
const EXPRESSION_START = "$" + "{{";
const RAW_INPUT = /\$\{\{\s*inputs\./u;
const ADMITTED_REVISION = `${EXPRESSION_START} needs.validate_inputs.outputs.revision }}`;

export class AssetContractError extends Error {}

function fail(message) {
  throw new AssetContractError(message);
}

function readRegular(file) {
  const descriptor = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
  try {
    if (!fs.fstatSync(descriptor).isFile()) fail(`asset is not a regular file: ${file}`);
    return fs.readFileSync(descriptor, "utf8");
  } finally {
    fs.closeSync(descriptor);
  }
}

export function parseWorkflow(source) {
  const document = parseDocument(source, {
    merge: false,
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length) fail(`workflow YAML is invalid: ${document.errors[0].message}`);
  const value = document.toJS({ maxAliasCount: 0 });
  if (value == null || Array.isArray(value) || typeof value !== "object") {
    fail("workflow must be a mapping");
  }
  return value;
}

function workflowDocument() {
  return parseWorkflow(readRegular(WORKFLOW));
}

function stepsOf(job, name) {
  if (!Array.isArray(job?.steps)) fail(`job has no steps: ${name}`);
  return job.steps;
}

export function validateWorkflow(workflow) {
  const jobs = workflow.jobs;
  if (jobs == null || Array.isArray(jobs) || typeof jobs !== "object") {
    fail("workflow jobs are missing");
  }
  const admission = jobs.validate_inputs;
  if (admission == null || typeof admission !== "object") fail("input admission job is missing");
  const admissionSteps = stepsOf(admission, "validate_inputs");
  if (admissionSteps.some((step) => typeof step?.uses === "string")) {
    fail("input admission must run before any checkout-local action");
  }
  if (!OUTPUTS.every((name) => Object.hasOwn(admission.outputs ?? {}, name))) {
    fail("input admission outputs are incomplete");
  }
  let checkoutCount = 0;
  for (const [jobName, job] of Object.entries(jobs)) {
    const steps = stepsOf(job, jobName);
    if (jobName !== "validate_inputs") {
      const needs = Array.isArray(job.needs) ? job.needs : [job.needs];
      if (!needs.includes("validate_inputs")) fail(`${jobName} bypasses input admission`);
    }
    for (const step of steps) {
      if (typeof step?.run === "string" && step.run.includes(EXPRESSION_START)) {
        fail(`${jobName} run source directly interpolates an expression`);
      }
      if (typeof step?.uses === "string") {
        if (!step.uses.startsWith("./") && !REMOTE_ACTION.test(step.uses)) {
          fail(`${jobName} uses an unpinned remote action`);
        }
        if (step.uses.startsWith("actions/checkout@")) {
          checkoutCount += 1;
          if (step.with?.ref !== ADMITTED_REVISION) {
            fail(`${jobName} checkout does not consume the admitted revision`);
          }
        }
      }
      for (const value of Object.values(step?.env ?? {})) {
        if (typeof value === "string" && RAW_INPUT.test(value) && jobName !== "validate_inputs") {
          fail(`${jobName} consumes raw dispatch input outside admission`);
        }
      }
    }
  }
  if (checkoutCount === 0) fail("workflow has no admitted checkout boundary");
}

function powershellSources(workflow) {
  const result = [];
  for (const file of fs.readdirSync(ASSET_ROOT).sort()) {
    if (file.toLowerCase().endsWith(".ps1")) {
      result.push({ name: `assets/${file}`, source: readRegular(path.join(ASSET_ROOT, file)) });
    }
  }
  for (const [jobName, job] of Object.entries(workflow.jobs)) {
    for (const step of stepsOf(job, jobName)) {
      const shell = typeof step?.shell === "string" ? step.shell.toLowerCase() : "";
      if (
        (shell.startsWith("pwsh") || shell.startsWith("powershell")) &&
        typeof step.run === "string"
      ) {
        result.push({ name: `workflow:${jobName}:${step.name ?? "unnamed"}`, source: step.run });
      }
    }
  }
  if (result.length === 0) fail("no PowerShell assets were found");
  return result;
}

function main() {
  const workflow = workflowDocument();
  validateWorkflow(workflow);
  const scripts = powershellSources(workflow);
  if (process.argv[2] === "--powershell-json") {
    process.stdout.write(`${JSON.stringify(scripts)}\n`);
    return;
  }
  if (process.argv.length !== 2)
    fail("usage: windows-installer-assets-contract.mjs [--powershell-json]");
  process.stdout.write(`windows-installer-assets: PASS powershell=${scripts.length}\n`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    const message = error instanceof Error ? error.message : "asset validation failed";
    process.stderr.write(`windows-installer-assets: FAIL: ${message}\n`);
    process.exitCode = 1;
  }
}
