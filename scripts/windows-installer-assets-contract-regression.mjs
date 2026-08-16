#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  AssetContractError,
  parseWorkflow,
  validateWorkflow,
} from "./windows-installer-assets-contract.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const EXPRESSION_START = "$" + "{{";
const SOURCE = fs.readFileSync(
  path.join(ROOT, "skills/building-flutter-apps/assets/windows-installer-workflow.yml"),
  "utf8",
);

function expectFailure(workflow, expected) {
  try {
    validateWorkflow(workflow);
  } catch (error) {
    if (!(error instanceof AssetContractError) || !error.message.includes(expected)) throw error;
    return;
  }
  throw new Error(`Windows asset mutation was accepted: ${expected}`);
}

function fixture() {
  return structuredClone(parseWorkflow(SOURCE));
}

validateWorkflow(fixture());

const directExpression = fixture();
directExpression.jobs.publish.steps.find((step) => typeof step.run === "string").run +=
  `\nWrite-Output '${EXPRESSION_START} inputs.version }}'`;
expectFailure(directExpression, "directly interpolates");

const earlyCheckout = fixture();
earlyCheckout.jobs.validate_inputs.steps.unshift({ uses: `actions/checkout@${"a".repeat(40)}` });
expectFailure(earlyCheckout, "before any checkout");

const bypass = fixture();
bypass.jobs.publish.needs = ["admission"];
expectFailure(bypass, "bypasses input admission");

const floatingAction = fixture();
floatingAction.jobs.publish.steps.find((step) => step.uses?.startsWith("actions/checkout@")).uses =
  "actions/checkout@main";
expectFailure(floatingAction, "unpinned remote action");

const wrongRevision = fixture();
wrongRevision.jobs.publish.steps.find((step) =>
  step.uses?.startsWith("actions/checkout@"),
).with.ref = "main";
expectFailure(wrongRevision, "admitted revision");

const rawInput = fixture();
rawInput.jobs.publish.steps.find((step) => typeof step.run === "string").env.DISPATCH_VERSION =
  `${EXPRESSION_START} inputs.version }}`;
expectFailure(rawInput, "raw dispatch input");

process.stdout.write("windows-installer-assets-regressions: PASS\n");
