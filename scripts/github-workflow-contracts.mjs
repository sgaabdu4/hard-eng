#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDocument } from "yaml";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CONTRACT_WORKFLOW = path.join(ROOT, ".github/workflows/check-skill-contracts.yml");
const REMOTE_ACTION = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[0-9a-f]{40}$/u;
const PLATFORM_ROWS = [
  ["ubuntu-24.04", "x64", "full"],
  ["ubuntu-24.04-arm", "arm64", "setup"],
  ["macos-15-intel", "x64", "setup"],
  ["macos-15", "arm64", "full"],
];

export class WorkflowContractError extends Error {}

function fail(message) {
  throw new WorkflowContractError(message);
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

export function validateContractWorkflow(workflow) {
  const job = workflow.jobs?.["hard-eng"];
  if (job == null || typeof job !== "object") fail("Hard Eng job is missing");
  const expressionStart = "$" + "{{";
  const matrixExpression = `${expressionStart} matrix.os }}`;
  const expectedName = `Hard Eng (${matrixExpression}, ${expressionStart} matrix.arch }}, ${expressionStart} matrix.scope }})`;
  const strategy = job.strategy;
  if (strategy == null || typeof strategy !== "object" || strategy["fail-fast"] !== false) {
    fail("Hard Eng platform matrix must keep independent failures visible");
  }
  const platforms = strategy.matrix?.include;
  if (
    !Array.isArray(platforms) ||
    JSON.stringify(platforms.map((row) => [row?.os, row?.arch, row?.scope])) !==
      JSON.stringify(PLATFORM_ROWS)
  ) {
    fail("Hard Eng matrix must cover Linux/macOS x64 and ARM64 with efficient scopes");
  }
  if (job["runs-on"] !== matrixExpression) fail("Hard Eng job must run on the matrix OS");
  if (job.name !== expectedName) {
    fail("Hard Eng job name must identify its OS, architecture, and scope");
  }
  if (workflow.permissions?.contents !== "read") fail("workflow permissions must remain read-only");
  const windows = workflow.jobs?.["windows-assets"];
  if (
    windows?.["runs-on"] !== "windows-2025" ||
    windows?.name !== "Windows installer assets (native PowerShell)"
  ) {
    fail("Windows asset job must use the current native Windows x64 runner");
  }
  const windowsSteps = Array.isArray(windows.steps) ? windows.steps : [];
  const nativeStep = windowsSteps.find(
    (step) => step?.name === "Parse managed PowerShell assets natively",
  );
  if (
    nativeStep?.shell !== "pwsh" ||
    nativeStep?.run !== "./scripts/parse-windows-installer-powershell.ps1"
  ) {
    fail("Windows asset job must parse PowerShell with native PowerShell");
  }
  for (const owner of [job, windows]) {
    const steps = Array.isArray(owner?.steps) ? owner.steps : [];
    const nodeStep = steps.find((step) => step?.uses?.startsWith("actions/setup-node@"));
    if (nodeStep?.with?.["node-version"] !== 26) fail("workflow Node version must match setup");
    for (const step of steps) {
      if (
        typeof step?.uses === "string" &&
        !step.uses.startsWith("./") &&
        !REMOTE_ACTION.test(step.uses)
      ) {
        fail("workflow actions must use full immutable commit pins");
      }
    }
  }
}

export function main() {
  validateContractWorkflow(parseWorkflow(fs.readFileSync(CONTRACT_WORKFLOW, "utf8")));
  process.stdout.write("github-workflow-contracts: PASS platforms=2\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    const message = error instanceof Error ? error.message : "workflow validation failed";
    process.stderr.write(`github-workflow-contracts: FAIL: ${message}\n`);
    process.exitCode = 1;
  }
}
