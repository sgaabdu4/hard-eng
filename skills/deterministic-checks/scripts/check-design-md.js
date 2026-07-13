#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

function reportExitCode(report) {
  const errors = report?.summary?.errors;
  const warnings = report?.summary?.warnings;
  if (!Number.isInteger(errors) || !Number.isInteger(warnings)) return 1;
  return errors || warnings ? 1 : 0;
}

function main() {
  const designPath = path.resolve(process.argv[2] || "DESIGN.md");
  const npx = process.platform === "win32" ? "npx.cmd" : "npx";
  const result = spawnSync(npx, ["--yes", "-p", "@google/design.md", "designmd", "lint", designPath], {
    encoding: "utf8",
  });

  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) {
    console.error(`design-md: FAIL | ${result.error.message}`);
    return 1;
  }
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.status !== 0) {
    console.error(`design-md: FAIL | linter exit ${result.status}`);
    return 1;
  }

  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch (error) {
    console.error(`design-md: FAIL | invalid JSON report: ${error.message}`);
    return 1;
  }

  if (reportExitCode(report)) {
    console.error(`design-md: FAIL | errors=${report.summary?.errors} warnings=${report.summary?.warnings}`);
    return 1;
  }
  console.log("design-md: PASS");
  return 0;
}

module.exports = { reportExitCode };

if (require.main === module) process.exit(main());
