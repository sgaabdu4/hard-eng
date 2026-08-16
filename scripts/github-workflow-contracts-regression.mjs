#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseWorkflow,
  validateContractWorkflow,
  WorkflowContractError,
} from "./github-workflow-contracts.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SOURCE = fs.readFileSync(
  path.join(ROOT, ".github/workflows/check-skill-contracts.yml"),
  "utf8",
);

function clone(value) {
  return structuredClone(value);
}

function expectFailure(value, expected) {
  try {
    validateContractWorkflow(value);
  } catch (error) {
    if (!(error instanceof WorkflowContractError) || !error.message.includes(expected)) throw error;
    return;
  }
  throw new Error(`workflow mutation was accepted: ${expected}`);
}

const workflow = parseWorkflow(SOURCE);
validateContractWorkflow(workflow);

const missingMac = clone(workflow);
missingMac.jobs["hard-eng"].strategy.matrix.include = missingMac.jobs[
  "hard-eng"
].strategy.matrix.include.filter((row) => !row.os.startsWith("macos-"));
expectFailure(missingMac, "Linux/macOS");

const missingArm = clone(workflow);
missingArm.jobs["hard-eng"].strategy.matrix.include = missingArm.jobs[
  "hard-eng"
].strategy.matrix.include.filter((row) => row.arch !== "arm64");
expectFailure(missingArm, "ARM64");

const fixedRunner = clone(workflow);
fixedRunner.jobs["hard-eng"]["runs-on"] = "ubuntu-latest";
expectFailure(fixedRunner, "matrix OS");

const failFast = clone(workflow);
failFast.jobs["hard-eng"].strategy["fail-fast"] = true;
expectFailure(failFast, "independent failures");

const missingWindows = clone(workflow);
delete missingWindows.jobs["windows-assets"];
expectFailure(missingWindows, "native Windows");

const floatingAction = clone(workflow);
floatingAction.jobs["hard-eng"].steps.find((step) =>
  step.uses?.startsWith("actions/checkout@"),
).uses = "actions/checkout@main";
expectFailure(floatingAction, "immutable commit pins");

const fakeNative = clone(workflow);
fakeNative.jobs["windows-assets"].steps.find(
  (step) => step.name === "Parse managed PowerShell assets natively",
).shell = "bash";
expectFailure(fakeNative, "native PowerShell");

process.stdout.write("github-workflow-contract-regressions: PASS\n");
