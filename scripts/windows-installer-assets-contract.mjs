#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseWorkflowYaml } from "./workflow-yaml.mjs";

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
  return parseWorkflowYaml(source, fail);
}

function workflowDocument() {
  return parseWorkflow(readRegular(WORKFLOW));
}

function stepsOf(job, name) {
  if (!Array.isArray(job?.steps)) fail(`job has no steps: ${name}`);
  return job.steps;
}

function jobsOf(workflow) {
  const jobs = workflow.jobs;
  if (jobs == null || Array.isArray(jobs) || typeof jobs !== "object") {
    fail("workflow jobs are missing");
  }
  return jobs;
}

function admissionJob(jobs) {
  const admission = jobs.validate_inputs;
  if (admission == null || typeof admission !== "object") fail("input admission job is missing");
  return admission;
}

function validateAdmission(admission) {
  const admissionSteps = stepsOf(admission, "validate_inputs");
  if (admissionSteps.some((step) => typeof step?.uses === "string")) {
    fail("input admission must run before any checkout-local action");
  }
  if (!OUTPUTS.every((name) => Object.hasOwn(admission.outputs ?? {}, name))) {
    fail("input admission outputs are incomplete");
  }
}

function validateJobDependency(jobName, job) {
  const needs = Array.isArray(job.needs) ? job.needs : [job.needs];
  if (!needs.includes("validate_inputs")) fail(`${jobName} bypasses input admission`);
}

function validateRunSource(jobName, step) {
  if (typeof step?.run === "string" && step.run.includes(EXPRESSION_START)) {
    fail(`${jobName} run source directly interpolates an expression`);
  }
}

function validateRemoteAction(jobName, uses) {
  if (!uses.startsWith("./") && !REMOTE_ACTION.test(uses)) {
    fail(`${jobName} uses an unpinned remote action`);
  }
}

function validateCheckout(jobName, step) {
  if (!step.uses.startsWith("actions/checkout@")) return false;
  if (step.with?.ref !== ADMITTED_REVISION) {
    fail(`${jobName} checkout does not consume the admitted revision`);
  }
  return true;
}

function validateAction(jobName, step) {
  if (typeof step?.uses !== "string") return false;
  validateRemoteAction(jobName, step.uses);
  return validateCheckout(jobName, step);
}

function validateEnvironment(jobName, step) {
  for (const value of environmentValues(step)) {
    if (rawInput(value)) {
      fail(`${jobName} consumes raw dispatch input outside admission`);
    }
  }
}

function environmentValues(step) {
  return Object.values(step?.env ?? {});
}

function rawInput(value) {
  return typeof value === "string" && RAW_INPUT.test(value);
}

function validateJobSteps(jobName, job, admission) {
  let checkoutCount = 0;
  for (const step of stepsOf(job, jobName)) {
    validateRunSource(jobName, step);
    if (validateAction(jobName, step)) checkoutCount += 1;
    if (!admission) validateEnvironment(jobName, step);
  }
  return checkoutCount;
}

export function validateWorkflow(workflow) {
  const jobs = jobsOf(workflow);
  validateAdmission(admissionJob(jobs));
  let checkoutCount = 0;
  for (const [jobName, job] of Object.entries(jobs)) {
    const admission = jobName === "validate_inputs";
    if (!admission) validateJobDependency(jobName, job);
    checkoutCount += validateJobSteps(jobName, job, admission);
  }
  if (checkoutCount === 0) fail("workflow has no admitted checkout boundary");
}

function assetPowerShellSources() {
  const result = [];
  for (const file of fs.readdirSync(ASSET_ROOT).sort()) {
    if (file.toLowerCase().endsWith(".ps1")) {
      result.push({ name: `assets/${file}`, source: readRegular(path.join(ASSET_ROOT, file)) });
    }
  }
  return result;
}

function shellName(step) {
  return typeof step?.shell === "string" ? step.shell.toLowerCase() : "";
}

function isPowerShell(shell) {
  return shell.startsWith("pwsh") || shell.startsWith("powershell");
}

function powerShellStep(jobName, step) {
  if (!isPowerShell(shellName(step))) return null;
  if (typeof step.run !== "string") return null;
  return { name: `workflow:${jobName}:${step.name ?? "unnamed"}`, source: step.run };
}

function workflowPowerShellSources(workflow) {
  const result = [];
  for (const [jobName, job] of Object.entries(workflow.jobs)) {
    for (const step of stepsOf(job, jobName)) {
      const source = powerShellStep(jobName, step);
      if (source !== null) result.push(source);
    }
  }
  return result;
}

function powershellSources(workflow) {
  const result = [...assetPowerShellSources(), ...workflowPowerShellSources(workflow)];
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
