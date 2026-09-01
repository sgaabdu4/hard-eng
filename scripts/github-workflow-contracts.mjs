#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseWorkflowYaml } from "./workflow-yaml.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CONTRACT_WORKFLOW = path.join(ROOT, ".github/workflows/check-skill-contracts.yml");
const REMOTE_ACTION = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[0-9a-f]{40}$/u;
const PLATFORM_ROWS = [
  ["ubuntu-24.04", "x64", "full"],
  ["ubuntu-24.04-arm", "arm64", "setup"],
  ["macos-15-intel", "x64", "setup"],
  ["macos-15", "arm64", "full"],
];
const WALKTHROUGH_TOOLCHAIN_REQUIREMENTS = [
  ["command -v ffmpeg", "walkthrough toolchain must verify both ffmpeg and ffprobe"],
  ["command -v ffprobe", "walkthrough toolchain must verify both ffmpeg and ffprobe"],
  [
    "--timeout 900 -- sudo apt-get",
    "walkthrough toolchain must allow the measured 900-second Ubuntu install bound",
  ],
  ["Acquire::Retries=3", "walkthrough toolchain must retry failed Ubuntu package downloads"],
  [
    "--no-install-recommends ffmpeg",
    "walkthrough toolchain must keep the Ubuntu FFmpeg dependency set minimal",
  ],
];

export class WorkflowContractError extends Error {}

function fail(message) {
  throw new WorkflowContractError(message);
}

export function parseWorkflow(source) {
  return parseWorkflowYaml(source, fail);
}

function mapping(value, message) {
  if (value == null || Array.isArray(value) || typeof value !== "object") fail(message);
  return value;
}

function validateHardEngMatrix(job) {
  const expressionStart = "$" + "{{";
  const strategy = mapping(job.strategy, "Hard Eng platform matrix is missing");
  if (strategy["fail-fast"] !== false) {
    fail("Hard Eng platform matrix must keep independent failures visible");
  }
  const platforms = matrixPlatforms(strategy);
  if (JSON.stringify(platformRows(platforms)) !== JSON.stringify(PLATFORM_ROWS)) {
    fail("Hard Eng matrix must cover Linux/macOS x64 and ARM64 with efficient scopes");
  }
  return expressionStart;
}

function matrixPlatforms(strategy) {
  const platforms = strategy.matrix?.include;
  if (!Array.isArray(platforms)) {
    fail("Hard Eng matrix must cover Linux/macOS x64 and ARM64 with efficient scopes");
  }
  return platforms;
}

function platformRows(platforms) {
  return platforms.map((row) => [row?.os, row?.arch, row?.scope]);
}

function validateHardEngRunner(job, expressionStart) {
  const matrixExpression = `${expressionStart} matrix.os }}`;
  const expectedName = `Hard Eng (${matrixExpression}, ${expressionStart} matrix.arch }}, ${expressionStart} matrix.scope }})`;
  if (job["runs-on"] !== matrixExpression) fail("Hard Eng job must run on the matrix OS");
  if (job.name !== expectedName) {
    fail("Hard Eng job name must identify its OS, architecture, and scope");
  }
}

function windowsJob(workflow) {
  const message = "Windows asset job must use the current native Windows x64 runner";
  const windows = mapping(workflow.jobs?.["windows-assets"], message);
  if (windows["runs-on"] !== "windows-2025") {
    fail(message);
  }
  if (windows.name !== "Windows installer assets (native PowerShell)") {
    fail("Windows asset job must use the current native Windows x64 runner");
  }
  return windows;
}

function validateNativeWindowsStep(windows) {
  const nativeStep = ownerSteps(windows).find(
    (step) => step?.name === "Parse managed PowerShell assets natively",
  );
  if (nativeStep?.shell !== "pwsh") {
    fail("Windows asset job must parse PowerShell with native PowerShell");
  }
  if (nativeStep.run !== "./scripts/parse-windows-installer-powershell.ps1") {
    fail("Windows asset job must parse PowerShell with native PowerShell");
  }
}

function actionReference(step) {
  return typeof step?.uses === "string" ? step.uses : null;
}

function validateActionPin(step) {
  const uses = actionReference(step);
  if (uses === null) return;
  if (uses.startsWith("./")) return;
  if (!REMOTE_ACTION.test(uses)) fail("workflow actions must use full immutable commit pins");
}

function ownerSteps(owner) {
  return Array.isArray(owner?.steps) ? owner.steps : [];
}

function nodeVersion(steps) {
  const nodeStep = steps.find((step) => actionReference(step)?.startsWith("actions/setup-node@"));
  return nodeStep?.with?.["node-version"];
}

function validateOwnerSteps(owner) {
  const steps = ownerSteps(owner);
  if (nodeVersion(steps) !== 26) fail("workflow Node version must match setup");
  for (const step of steps) validateActionPin(step);
}

function validateWalkthroughToolchain(steps) {
  const step = steps.find(
    (candidate) => candidate?.name === "Install walkthrough recorder toolchain",
  );
  const command = typeof step?.run === "string" ? step.run : "";
  const missing = WALKTHROUGH_TOOLCHAIN_REQUIREMENTS.find(([anchor]) => !command.includes(anchor));
  if (missing) fail(missing[1]);
}

export function validateContractWorkflow(workflow) {
  const job = mapping(workflow.jobs?.["hard-eng"], "Hard Eng job is missing");
  validateHardEngRunner(job, validateHardEngMatrix(job));
  if (workflow.permissions?.contents !== "read") fail("workflow permissions must remain read-only");
  const windows = windowsJob(workflow);
  validateNativeWindowsStep(windows);
  validateOwnerSteps(job);
  validateWalkthroughToolchain(ownerSteps(job));
  validateOwnerSteps(windows);
}

function main() {
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
