#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseWorkflowYaml } from "./workflow-yaml.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const RELEASE_WORKFLOW = path.join(ROOT, ".github/workflows/check-skill-contracts.yml");
const UPDATE_WORKFLOW = path.join(ROOT, ".github/workflows/update-managed-skills.yml");
const MAINTENANCE_WORKFLOW = path.join(ROOT, ".github/workflows/codex-maintenance.yml");
const REMOTE_ACTION = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[0-9a-f]{40}$/u;
const REQUIRED_GATE_JOBS = ["hard-eng", "windows-assets"];
const RELEASE_JOB = "release";
const RELEASE_EVENT = "hard-eng-release";
const HANDOFF = "maintenance release handoff must";
const EXPRESSION_START = "$" + "{{";
const SOURCE_REF = `${EXPRESSION_START} env.SOURCE_SHA }}`;
const RELEASE_IF = `${EXPRESSION_START} (github.event_name == 'push' && github.ref == 'refs/heads/main') || (github.event_name == 'repository_dispatch' && github.event.action == '${RELEASE_EVENT}' && github.actor == 'github-actions[bot]' && github.ref == 'refs/heads/main' && github.event.client_payload.sha != '') }}`;
const SOURCE_EXPRESSION = `${EXPRESSION_START} github.event_name == 'repository_dispatch' && github.event.client_payload.sha || github.sha }}`;
const RELEASE_STEP_NAMES = [
  "Check out repository",
  "Set up Node",
  "Validate source event",
  "Build deterministic release",
  "Check existing release",
  "Check source against current main",
  "Check release verification support",
  "Claim exact tag commit",
  "Create draft release",
  "Upload missing release assets",
  "Verify draft and publish immutable release",
  "Verify immutable release",
];
const RELEASE_MUTATION_CONDITIONS = new Map([
  ["Check source against current main", "steps.existing-release.outputs.action != 'reuse'"],
  ["Create draft release", "steps.existing-release.outputs.action == 'create'"],
  ["Upload missing release assets", "steps.existing-release.outputs.action != 'reuse'"],
  [
    "Verify draft and publish immutable release",
    "steps.existing-release.outputs.action != 'reuse'",
  ],
]);
const RELEASE_PERMISSION_NAMES = new Set(["contents", "attestations"]);
const UPDATE_STEP_NAMES = [
  "Check out default branch",
  "Set up Node.js",
  "Check mutation readiness",
  "Install pinned repository checks",
  "Map checkout to the global agents home",
  "Update every locked skill",
  "Validate and commit updates",
  "Read back remote main after push",
  "Dispatch canonical release for exact SHA",
];

export class ReleaseWorkflowContractError extends Error {}

function fail(message) {
  throw new ReleaseWorkflowContractError(message);
}

function mapping(value, message) {
  if (value == null || Array.isArray(value) || typeof value !== "object") fail(message);
  return value;
}

function stepsOf(job, label = "workflow") {
  if (!Array.isArray(job?.steps) || job.steps.length === 0) fail(`${label} steps are missing`);
  return job.steps;
}

function namedStep(steps, name) {
  const step = steps.find((candidate) => candidate?.name === name);
  if (step == null) fail(`workflow step is missing: ${name}`);
  return step;
}

function runText(step) {
  return typeof step?.run === "string" ? step.run : "";
}

function hereDocDelimiter(line) {
  const match = line.match(/<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_-]*)\1/u);
  return match?.[2];
}

function skipHereDocLine(state, line) {
  if (line.trim() === state.delimiter) state.delimiter = undefined;
}

function appendShellLine(state, line) {
  if (/^\s*#/u.test(line)) return;
  state.executable.push(line);
  state.delimiter = hereDocDelimiter(line);
}

function executableLines(step) {
  const state = { delimiter: undefined, executable: [] };
  for (const line of runText(step).split(/\r?\n/u)) {
    if (state.delimiter === undefined) appendShellLine(state, line);
    else skipHereDocLine(state, line);
  }
  return state.executable;
}

function executableText(step) {
  return executableLines(step).join("\n");
}

function commandPattern(command) {
  const escaped = command.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  return new RegExp(
    `(?:^|\\b(?:if\\s+!?|then|else|do)\\s*|[;&|]\\s*|\\$\\(\\s*)\\s*${escaped}(?:\\s|$)`,
    "mu",
  );
}

function commandLineIndex(step, command) {
  const pattern = commandPattern(command);
  return executableLines(step).findIndex((line) => pattern.test(line));
}

function hasCommand(step, command) {
  return commandLineIndex(step, command) >= 0;
}

function commandsInOrder(step, first, second) {
  const firstIndex = commandLineIndex(step, first);
  const secondIndex = commandLineIndex(step, second);
  return firstIndex >= 0 && secondIndex > firstIndex;
}

function hasText(step, pattern) {
  return pattern.test(executableText(step));
}

function actionOf(step) {
  return typeof step?.uses === "string" ? step.uses : undefined;
}

function validateRemoteAction(jobName, step) {
  const action = actionOf(step);
  if (action === undefined || action.startsWith("./")) return;
  if (!REMOTE_ACTION.test(action)) fail(`${jobName} uses an unpinned remote action`);
}

function validateActions(workflow) {
  for (const [jobName, job] of Object.entries(workflow.jobs ?? {})) {
    for (const step of stepsOf(job, `${jobName} job`)) validateRemoteAction(jobName, step);
  }
}

function validateJobFailClosed(name, job) {
  if (job?.["continue-on-error"] === true) fail(`${name} job must fail closed`);
  if (stepsOf(job, `${name} job`).some((step) => step?.["continue-on-error"] === true)) {
    fail(`${name} steps must fail closed`);
  }
}

function validateRequiredGateNames(jobs) {
  for (const jobName of REQUIRED_GATE_JOBS) {
    if (jobs[jobName] == null) fail(`required CI job is missing: ${jobName}`);
    validateJobFailClosed(jobName, jobs[jobName]);
  }
}

function validateHardEngStrategy(job) {
  if (job.strategy?.["fail-fast"] !== false) fail("Hard Eng matrix must keep fail-fast disabled");
}

function validateHardEngMatrixShape(job) {
  const matrix = job.strategy?.matrix?.include;
  if (!Array.isArray(matrix) || matrix.length !== 4)
    fail("Hard Eng matrix must retain all four platform gates");
}

function validateHardEngMatrix(job) {
  validateHardEngStrategy(job);
  validateHardEngMatrixShape(job);
}

function checkoutOptions(name, checkout) {
  if (checkout.with === undefined) fail(`${name} checkout options are missing`);
  return checkout.with;
}

function validateCheckoutReference(name, checkout) {
  const options = checkoutOptions(name, checkout);
  if (options.ref !== SOURCE_REF) fail(`${name} checkout must use the source SHA`);
  if (options["fetch-depth"] !== 0) fail(`${name} checkout must fetch full history`);
}

function hasSourceComparison(validation) {
  return hasCommand(validation, "git rev-parse") && hasText(validation, /SOURCE_SHA/u);
}

function validateSourceValidation(name, validation) {
  if (validation.shell !== "bash") fail(`${name} source validation must use bash`);
  if (!hasSourceComparison(validation)) {
    fail(`${name} source validation must compare the checked-out source SHA`);
  }
  if (!hasCommand(validation, "node scripts/release-builder.mjs validate-event")) {
    fail(`${name} source validation must use the release event validator`);
  }
}

function validateSourceCheckout(name, job, validationName = "Validate source checkout") {
  const steps = stepsOf(job, `${name} job`);
  validateCheckoutReference(name, namedStep(steps, "Check out repository"));
  validateSourceValidation(name, namedStep(steps, validationName));
}

function validateRequiredGates(workflow) {
  const jobs = mapping(workflow.jobs, "workflow jobs are missing");
  validateRequiredGateNames(jobs);
  validateHardEngMatrix(jobs["hard-eng"]);
  validateSourceCheckout("hard-eng", jobs["hard-eng"]);
  validateSourceCheckout("windows-assets", jobs["windows-assets"]);
}

function validatePushTrigger(triggers) {
  const pushBranches = triggers.push?.branches;
  if (!Array.isArray(pushBranches) || !pushBranches.includes("main"))
    fail("workflow must trigger on main pushes");
}

function validateDispatchTrigger(triggers) {
  const dispatchTypes = triggers.repository_dispatch?.types;
  if (!Array.isArray(dispatchTypes) || !dispatchTypes.includes(RELEASE_EVENT)) {
    fail("workflow must accept only the named release dispatch event");
  }
}

function validateWorkflowTriggers(workflow) {
  const triggers = mapping(workflow.on, "workflow triggers are missing");
  validatePushTrigger(triggers);
  validateDispatchTrigger(triggers);
}

function validateConcurrency(workflow) {
  const concurrency = mapping(workflow.concurrency, "release concurrency is missing");
  if (concurrency.group !== `hard-eng-release-${SOURCE_EXPRESSION}`) {
    fail("release concurrency must be keyed by the source SHA");
  }
  if (concurrency["cancel-in-progress"] !== false)
    fail("release concurrency must not cancel source runs");
}

function validateNeeds(release) {
  const needs = Array.isArray(release.needs) ? release.needs : [release.needs];
  if (JSON.stringify(needs) !== JSON.stringify(REQUIRED_GATE_JOBS)) {
    fail("release job must need every required Linux/macOS/Windows CI job");
  }
}

function validateWorkflowPermissions(workflow) {
  if (JSON.stringify(workflow.permissions) !== JSON.stringify({ contents: "read" })) {
    fail("workflow default permissions must remain contents read-only");
  }
}

function validateReleasePermissions(release) {
  const permissions = mapping(release.permissions, "release job permissions are missing");
  if (permissions.contents !== "write" || permissions.attestations !== "read") {
    fail("release job requires only release contents write and attestation read access");
  }
  if (!Object.keys(permissions).every((key) => RELEASE_PERMISSION_NAMES.has(key))) {
    fail("release job has broader permissions than release publication and verification need");
  }
}

function validateReleaseTrigger(release) {
  if (release.if !== RELEASE_IF)
    fail("release job must be gated to trusted main push or bot dispatch");
  if (release.if.includes("always()"))
    fail("release job must not bypass failed or skipped required jobs");
}

function validateStepSet(steps) {
  if (JSON.stringify(steps.map((step) => step?.name)) !== JSON.stringify(RELEASE_STEP_NAMES)) {
    fail("release job must keep the exact reviewed step set and order");
  }
}

function requireRun(step, description) {
  if (runText(step).trim() === "") fail(`${description} must execute a command`);
  if (!hasText(step, /set -euo pipefail/u)) fail(`${description} must fail closed`);
}

function validateSourceEventCommand(step) {
  if (!hasCommand(step, "node scripts/release-builder.mjs validate-event")) {
    fail("release source validation must use the release event validator");
  }
  if (!hasText(step, /checked_out_sha|SOURCE_SHA/u))
    fail("release source validation must bind the checkout SHA");
}

const DRAFT_AWARE_RELEASE_ID_CHECKS = [
  (step) => hasCommand(step, "gh release view"),
  (step) => hasText(step, /--json\s+databaseId/u),
  (step) => hasText(step, /\[\[\s*"\$release_id"\s*=~\s*\^\[1-9\]\[0-9\]\*\$\s*\]\]/u),
  (step) => hasCommand(step, "gh api"),
  (step) => hasText(step, /releases\/\$release_id/u),
  (step) => !hasText(step, /releases\/tags/u),
];

const RELEASE_COMMAND_CONTRACTS = [
  {
    name: "Build deterministic release",
    checks: [
      (step) => hasCommand(step, "node scripts/release-builder.mjs build"),
      (step) => hasText(step, /--commit\s+"\$SOURCE_SHA"/u),
      (step) => !hasText(step, /GITHUB_RUN_NUMBER/u),
    ],
    error: "release builder must bind the archive and manifest to SOURCE_SHA without run metadata",
  },
  {
    name: "Check existing release",
    checks: [
      ...DRAFT_AWARE_RELEASE_ID_CHECKS,
      (step) => hasCommand(step, "node scripts/release-builder.mjs classify"),
    ],
    error:
      "release retries must inspect and classify the draft-aware release ID before tag mutation",
  },
  {
    name: "Check source against current main",
    checks: [
      (step) => hasCommand(step, "gh api"),
      (step) => hasText(step, /git\/ref\/heads\/main/u),
      (step) => hasCommand(step, "git fetch"),
      (step) => hasCommand(step, "git merge-base --is-ancestor"),
      (step) => hasText(step, /\.github\/workflows/u),
      (step) => hasCommand(step, "git diff --quiet"),
    ],
    error:
      "release must prove SOURCE_SHA is an ancestor with matching workflow files before mutation",
  },
  {
    name: "Check release verification support",
    checks: [(step) => hasCommand(step, "gh release verify --help")],
    error: "release verification capability must be checked before any mutation",
  },
  {
    name: "Create draft release",
    checks: [
      (step) => hasCommand(step, "gh release create"),
      (step) => hasText(step, /--target\s+"\$SOURCE_SHA"/u),
      (step) => hasText(step, /--draft/u),
      (step) => hasText(step, /--prerelease/u),
    ],
    error: "release must create an exact-source draft prerelease",
  },
  {
    name: "Claim exact tag commit",
    checks: [
      (step) => hasCommand(step, "gh api"),
      (step) => hasCommand(step, "gh api --method POST"),
      (step) => hasText(step, /if\s+gh api --method POST/u),
      (step) => !hasText(step, /if\s+!\s+gh api --method POST/u),
      (step) => hasText(step, /git\/refs/u),
      (step) => hasText(step, /refs\/tags\/\$RELEASE_TAG/u),
      (step) => hasText(step, /sha=\$SOURCE_SHA/u),
      (step) => hasCommand(step, "node scripts/release-builder.mjs validate-tag"),
    ],
    error: "release must create or read and validate the exact tag commit before draft creation",
  },
  {
    name: "Upload missing release assets",
    checks: [
      (step) => hasCommand(step, "gh release upload"),
      (step) => hasText(step, /missing_assets|upload-assets/u),
      (step) => !hasText(step, /--clobber/u),
    ],
    error: "release must upload only the exact missing assets without overwriting",
  },
  {
    name: "Verify draft and publish immutable release",
    checks: [
      ...DRAFT_AWARE_RELEASE_ID_CHECKS,
      (step) => hasCommand(step, "node scripts/release-builder.mjs validate-tag"),
      (step) => hasCommand(step, "node scripts/release-builder.mjs verify-draft"),
      (step) => hasCommand(step, "gh release edit"),
      (step) => hasText(step, /--draft=false/u),
      (step) => hasText(step, /prepublish-tag\.json/u),
      (step) =>
        commandsInOrder(step, "node scripts/release-builder.mjs verify-draft", "gh release edit"),
    ],
    error:
      "release must prove the draft-aware release ID, exact tag, and assets immediately before publishing",
  },
  {
    name: "Verify immutable release",
    checks: [
      (step) => hasCommand(step, "gh api"),
      (step) => hasCommand(step, "gh release verify"),
      (step) => hasCommand(step, "node scripts/release-builder.mjs verify"),
      (step) => hasText(step, /--attestation/u),
      (step) => hasText(step, /final-tag\.json/u),
      (step) => hasCommand(step, "node scripts/release-builder.mjs validate-tag"),
    ],
    error: "release must verify immutable identity, assets, and attestation",
  },
];

function passesChecks(step, checks) {
  return checks.every((check) => check(step));
}

function validateCommandContracts(steps) {
  for (const contract of RELEASE_COMMAND_CONTRACTS) {
    const step = namedStep(steps, contract.name);
    if (!passesChecks(step, contract.checks)) fail(contract.error);
    requireRun(step, contract.name);
  }
  validateSourceEventCommand(namedStep(steps, "Validate source event"));
}

function validateMutationConditions(steps) {
  for (const [name, condition] of RELEASE_MUTATION_CONDITIONS) {
    if (namedStep(steps, name).if !== condition)
      fail("release mutations must use exact rerun conditions");
  }
}

function validateTagClaimOrder(steps) {
  const claimIndex = steps.findIndex((step) => step?.name === "Claim exact tag commit");
  const draftIndex = steps.findIndex((step) => step?.name === "Create draft release");
  if (claimIndex < 0 || draftIndex < 0 || claimIndex > draftIndex) {
    fail("exact tag claim must precede draft creation");
  }
}

function validateNoBypasses(steps) {
  const forbidden = /\|\|\s*true|--clobber|gh release delete|delete-asset|-X\s+DELETE/u;
  if (steps.some((step) => forbidden.test(executableText(step)))) {
    fail("release steps must not bypass errors, overwrite assets, or delete release state");
  }
}

function validateReleaseSteps(release) {
  const steps = stepsOf(release, "release job");
  validateJobFailClosed("release", release);
  validateStepSet(steps);
  validateCommandContracts(steps);
  validateMutationConditions(steps);
  validateTagClaimOrder(steps);
  validateNoBypasses(steps);
}

function releaseJob(workflow) {
  const release = mapping(workflow.jobs?.[RELEASE_JOB], "release job is missing");
  if (release["runs-on"] !== "ubuntu-24.04")
    fail("release job must use the pinned Linux release runner");
  return release;
}

function validateReleaseCheckout(release) {
  validateSourceCheckout("release", release, "Validate source event");
}

export function parseWorkflow(source) {
  return parseWorkflowYaml(source, fail);
}

export function validateReleaseWorkflow(workflow) {
  validateWorkflowTriggers(workflow);
  validateConcurrency(workflow);
  validateWorkflowPermissions(workflow);
  validateRequiredGates(workflow);
  validateActions(workflow);
  const release = releaseJob(workflow);
  validateReleaseTrigger(release);
  validateNeeds(release);
  validateReleasePermissions(release);
  validateReleaseCheckout(release);
  validateReleaseSteps(release);
  return true;
}

function validateUpdaterPermissions(workflow) {
  if (JSON.stringify(workflow.permissions) !== JSON.stringify({ contents: "write" })) {
    fail("managed-skill updater must have only contents write permission");
  }
}

function validateUpdaterTriggers(workflow) {
  const triggers = mapping(workflow.on, "managed-skill updater triggers are missing");
  if (
    !Array.isArray(triggers.schedule) ||
    triggers.schedule.length === 0 ||
    !Object.hasOwn(triggers, "workflow_dispatch")
  ) {
    fail("managed-skill updater must retain schedule and manual triggers");
  }
}

function validateUpdaterStepSet(steps) {
  if (JSON.stringify(steps.map((step) => step?.name)) !== JSON.stringify(UPDATE_STEP_NAMES)) {
    fail("managed-skill updater must keep its reviewed step set and order");
  }
}

function validateUpdaterCommitIdentity(step) {
  if (step.id !== "commit-updates") fail("managed-skill updater must record the changed commit");
}

function validateUpdaterCommitPush(step) {
  if (!hasCommand(step, "git push")) fail("managed-skill updater must push the changed commit");
}

function validateUpdaterCommitOutputs(step) {
  if (!hasText(step, /changed=false/u)) {
    fail("managed-skill updater must expose the no-change path");
  }
  if (!hasText(step, /sha=%s/u)) {
    fail("managed-skill updater must expose the exact pushed SHA");
  }
}

function validateUpdaterCommit(step) {
  requireRun(step, "managed-skill updater commit step");
  validateUpdaterCommitIdentity(step);
  validateUpdaterCommitPush(step);
  validateUpdaterCommitOutputs(step);
}

function validateUpdaterStepCondition(step) {
  if (step.if !== "steps.commit-updates.outputs.changed == 'true'") {
    fail("managed-skill updater readback and dispatch must require a changed commit");
  }
}

function validateUpdaterReadbackApi(step) {
  if (!hasCommand(step, "gh api")) fail("managed-skill updater must read back remote main");
}

function validateUpdaterReadbackReference(step) {
  if (!hasText(step, /git\/ref\/heads\/\$DEFAULT_BRANCH/u)) {
    fail("managed-skill updater must read back remote main");
  }
}

function validateUpdaterReadbackComparison(step) {
  if (!hasCommand(step, "test"))
    fail("managed-skill updater must compare remote main with the pushed SHA");
  if (!hasText(step, /EXPECTED_SHA/u)) {
    fail("managed-skill updater must compare remote main with the pushed SHA");
  }
}

function validateUpdaterReadback(step) {
  requireRun(step, "managed-skill updater readback step");
  validateUpdaterStepCondition(step);
  validateUpdaterReadbackApi(step);
  validateUpdaterReadbackReference(step);
  validateUpdaterReadbackComparison(step);
}

function validateUpdaterDispatchApi(step) {
  if (!hasCommand(step, "gh api --method POST")) {
    fail("managed-skill updater must dispatch through the GitHub API");
  }
  if (!hasText(step, /dispatches/u)) {
    fail("managed-skill updater must dispatch through the GitHub API");
  }
}

function validateUpdaterDispatchEvent(step) {
  if (!hasText(step, /event_type=hard-eng-release/u)) {
    fail("managed-skill updater must dispatch the named release event");
  }
}

function validateUpdaterDispatchSha(step) {
  if (!hasText(step, /client_payload\[sha\]=\$RELEASE_SHA/u)) {
    fail("managed-skill updater must dispatch the exact pushed SHA");
  }
}

function validateUpdaterDispatch(step) {
  requireRun(step, "managed-skill updater dispatch step");
  validateUpdaterStepCondition(step);
  validateUpdaterDispatchApi(step);
  validateUpdaterDispatchEvent(step);
  validateUpdaterDispatchSha(step);
}

function validateUpdaterCommands(steps) {
  validateUpdaterCommit(namedStep(steps, "Validate and commit updates"));
  validateUpdaterReadback(namedStep(steps, "Read back remote main after push"));
  validateUpdaterDispatch(namedStep(steps, "Dispatch canonical release for exact SHA"));
}

export function validateManagedSkillsWorkflow(workflow) {
  validateUpdaterTriggers(workflow);
  validateUpdaterPermissions(workflow);
  const update = mapping(workflow.jobs?.update, "managed-skill updater job is missing");
  validateJobFailClosed("managed-skill updater", update);
  validateUpdaterStepSet(stepsOf(update, "managed-skill updater job"));
  validateUpdaterCommands(stepsOf(update, "managed-skill updater job"));
  return true;
}
function validateMaintenanceTriggers(workflow) {
  const triggers = mapping(workflow.on, "maintenance workflow triggers are missing");
  requireAll(
    "maintenance workflow must retain schedule and manual triggers",
    Array.isArray(triggers.schedule),
    triggers.schedule?.length > 0,
    Object.hasOwn(triggers, "workflow_dispatch"),
  );
}
function requireAll(message, ...checks) {
  if (checks.includes(false)) fail(message);
}
function validateMaintenancePermissions(workflow, job) {
  const readOnly = { contents: "read", issues: "read", "pull-requests": "read" };
  const jobPermissions = { contents: "write", issues: "read", "pull-requests": "write" };
  requireAll(
    "maintenance workflow must keep its reviewed permissions",
    JSON.stringify([workflow.permissions, job.permissions]) ===
      JSON.stringify([readOnly, jobPermissions]),
  );
  requireAll(
    "maintenance release handoff must use the GitHub Actions bot token",
    job.env?.GH_TOKEN === `${EXPRESSION_START} github.token }}`,
  );
}
function validateMaintenanceQueue(step) {
  requireRun(step, "maintenance Dependabot queue step");
  requireAll(
    `${HANDOFF} use fail-closed bash`,
    step.shell === "bash",
    hasText(step, /set -euo pipefail/u),
  );
  requireAll(
    `${HANDOFF} retain reviewed squash auto-merge`,
    hasCommand(step, "gh pr merge"),
    hasText(step, /--auto/u),
    hasText(step, /--squash/u),
  );
  requireAll(
    `${HANDOFF} use a bounded merge wait`,
    hasText(step, /merge_deadline/u),
    hasText(step, /SECONDS/u),
  );
  requireAll(
    `${HANDOFF} read back merge and auto-merge state`,
    hasCommand(step, "gh pr view"),
    hasText(step, /state,mergeCommit/u),
    hasText(step, /autoMergeRequest/u),
  );
  requireAll(`${HANDOFF} validate the exact merge SHA`, hasText(step, /\^\[0-9a-f\]\{40\}\$/u));
  requireAll(
    `${HANDOFF} prove the merge is on the default branch`,
    hasCommand(step, "gh api"),
    hasText(step, /compare\/\$release_sha\.\.\.\$default_branch/u),
  );
  requireAll(
    `${HANDOFF} dispatch the exact merge SHA`,
    hasCommand(step, "gh api --method POST"),
    hasText(step, /dispatches/u),
    hasText(step, /event_type=hard-eng-release/u),
    hasText(step, /client_payload\[sha\]=\$release_sha/u),
  );
  requireAll(
    `${HANDOFF} disable unresolved auto-merges before exit`,
    hasCommand(step, "gh pr merge"),
    hasText(step, /--disable-auto/u),
  );
  validateNoBypasses([step]);
}
export function validateMaintenanceWorkflow(workflow) {
  validateMaintenanceTriggers(workflow);
  const maintain = mapping(workflow.jobs?.maintain, "maintenance job is missing");
  validateJobFailClosed("maintenance", maintain);
  validateMaintenancePermissions(workflow, maintain);
  validateMaintenanceQueue(
    namedStep(stepsOf(maintain, "maintenance job"), "Queue Dependabot pull requests"),
  );
  return true;
}
const readWorkflow = (file) => parseWorkflow(fs.readFileSync(file, "utf8"));
function main() {
  validateReleaseWorkflow(readWorkflow(RELEASE_WORKFLOW));
  validateManagedSkillsWorkflow(readWorkflow(UPDATE_WORKFLOW));
  validateMaintenanceWorkflow(readWorkflow(MAINTENANCE_WORKFLOW));
  process.stdout.write("release-workflow-contracts: PASS all-release-handoffs-verified\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main();
  } catch (error) {
    const message = error instanceof Error ? error.message : "release workflow validation failed";
    process.stderr.write(`release-workflow-contracts: FAIL: ${message}\n`);
    process.exitCode = 1;
  }
}
