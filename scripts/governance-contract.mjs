#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import YAML from "yaml";

const ROOT = resolve(import.meta.dirname, "..");
const OWNER = "@sgaabdu4";
const REQUIRED_OWNER_PATTERNS = new Set([
  "*",
  "/scripts/setup/",
  "/scripts/hooks/",
  "/scripts/enforcement_*.pl",
  "/.github/workflows/",
  "/.skill-lock.json",
  "/skills/appwrite-backend/",
  "/skills/building-flutter-apps/",
  "/skills/vercel-react-best-practices/",
  "/skills/building-flutter-apps/assets/",
  "/SECURITY.md",
  "/docs/security/",
]);
const REQUIRED_CHECKS = [
  "Hard Eng (ubuntu-24.04, x64, full)",
  "Hard Eng (ubuntu-24.04-arm, arm64, setup)",
  "Hard Eng (macos-15-intel, x64, setup)",
  "Hard Eng (macos-15, arm64, full)",
  "Windows installer assets (native PowerShell)",
];

function fail(message) {
  throw new Error(`governance-contract: FAIL: ${message}`);
}

export function validateCodeowners(source) {
  const entries = codeownerEntries(source);
  for (const pattern of REQUIRED_OWNER_PATTERNS) {
    const owners = entries.get(pattern);
    if (!owners?.includes(OWNER)) fail(`missing code owner for ${pattern}`);
  }
}

function codeownerEntries(source) {
  const entries = new Map();
  for (const raw of source.split(/\r?\n/u)) {
    const line = raw.trim();
    if (!isCodeownerEntry(line)) continue;
    const fields = line.split(/\s+/u);
    if (fields.length < 2) fail(`invalid CODEOWNERS line: ${line}`);
    entries.set(fields[0], fields.slice(1));
  }
  return entries;
}

function isCodeownerEntry(line) {
  return line.length > 0 && !line.startsWith("#");
}

function dependabotUpdates(source) {
  const value = YAML.parse(source);
  if (value?.version !== 2) fail("Dependabot schema must contain version 2 updates");
  if (!Array.isArray(value.updates)) fail("Dependabot schema must contain version 2 updates");
  return new Map(value.updates.map((entry) => [entry["package-ecosystem"], entry]));
}

function validateDependencySet(updates) {
  if (updates.size !== 2) fail("Dependabot must cover root npm and GitHub Actions");
  for (const ecosystem of ["github-actions", "npm"]) {
    if (!updates.has(ecosystem)) fail("Dependabot must cover root npm and GitHub Actions");
  }
}

function validateDependencyTarget(ecosystem, entry) {
  if (entry.directory !== "/" || entry["target-branch"] !== "main") {
    fail(`${ecosystem} Dependabot target must be root main`);
  }
}

function validateDependencySchedule(ecosystem, entry) {
  const schedule = entry.schedule ?? {};
  if (schedule.interval !== "weekly") {
    fail(`${ecosystem} Dependabot schedule must be weekly UTC`);
  }
  if (schedule.timezone !== "Etc/UTC") {
    fail(`${ecosystem} Dependabot schedule must be weekly UTC`);
  }
}

function validateDependencyUpdate(ecosystem, entry) {
  validateDependencyTarget(ecosystem, entry);
  validateDependencySchedule(ecosystem, entry);
  if (!Number.isInteger(entry["open-pull-requests-limit"])) {
    fail(`${ecosystem} Dependabot pull-request limit is missing`);
  }
}

export function validateDependabot(source) {
  const updates = dependabotUpdates(source);
  validateDependencySet(updates);
  for (const [ecosystem, entry] of updates) {
    validateDependencyUpdate(ecosystem, entry);
  }
}

function requireAnchors(source, anchors, label) {
  for (const anchor of anchors) {
    if (!source.includes(anchor)) fail(`${label} missing ${anchor}`);
  }
}

function validateSecurityDocs(security, threatModel) {
  requireAnchors(
    security,
    [
      "GitHub private vulnerability reporting",
      "Do not include credentials",
      "does not claim that private reporting",
      "release and update threat model",
    ],
    "SECURITY.md",
  );
  requireAnchors(
    threatModel,
    [
      "setup pins",
      "managed-skill trees",
      "Dispatch input",
      "process-group cleanup",
      "administrator readback",
    ],
    "threat model",
  );
}

function validateBranchPolicy(branchPolicy) {
  if (!branchPolicy.includes("does not claim the GitHub settings are configured")) {
    fail("branch policy claims unverified GitHub settings");
  }
  requireAnchors(
    branchPolicy,
    REQUIRED_CHECKS.map((check) => `\`${check}\``),
    "branch policy",
  );
  requireAnchors(
    branchPolicy,
    ["code-owner review", "Dismiss stale approvals", "Block force pushes", "updater identity"],
    "branch policy",
  );
}

export function validateDocs(security, threatModel, branchPolicy) {
  validateSecurityDocs(security, threatModel);
  validateBranchPolicy(branchPolicy);
}

function expectFailure(action, label) {
  try {
    action();
  } catch {
    return;
  }
  fail(`negative fixture passed: ${label}`);
}

function main() {
  const codeowners = readFileSync(resolve(ROOT, ".github/CODEOWNERS"), "utf8");
  const dependabot = readFileSync(resolve(ROOT, ".github/dependabot.yml"), "utf8");
  const security = readFileSync(resolve(ROOT, "SECURITY.md"), "utf8");
  const threatModel = readFileSync(
    resolve(ROOT, "docs/security/release-update-threat-model.md"),
    "utf8",
  );
  const branchPolicy = readFileSync(resolve(ROOT, ".github/BRANCH_PROTECTION.md"), "utf8");
  validateCodeowners(codeowners);
  validateDependabot(dependabot);
  validateDocs(security, threatModel, branchPolicy);
  expectFailure(
    () => validateCodeowners(codeowners.replace("/scripts/setup/ @sgaabdu4", "")),
    "missing setup owner",
  );
  expectFailure(
    () => validateDependabot(dependabot.replace("target-branch: main", "target-branch: release")),
    "wrong dependency target",
  );
  expectFailure(
    () => validateDocs(security, threatModel, branchPolicy.replace("does not claim", "claims")),
    "unverified settings claim",
  );
  process.stdout.write("governance-contract: PASS\n");
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
