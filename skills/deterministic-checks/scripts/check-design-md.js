#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const validCount = (value) => Number.isInteger(value);
const summaryCounts = (report) => {
  const summary = report?.summary ?? {};
  return [summary.errors, summary.warnings];
};

function reportExitCode(report) {
  const counts = summaryCounts(report);
  return counts.every(validCount) && !counts.some(Boolean) ? 0 : 1;
}

function runLinter(designPath) {
  const npx = process.platform === "win32" ? "npx.cmd" : "npx";
  return spawnSync(
    npx,
    ["--yes", "-p", "@google/design.md@0.4.0", "designmd", "lint", designPath],
    { encoding: "utf8" },
  );
}

function forwardOutput(result) {
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.stdout) process.stdout.write(result.stdout);
}

function executionError(result) {
  if (result.error) {
    return `design-md: FAIL | ${result.error.message}`;
  }
  if (result.status !== 0) {
    return `design-md: FAIL | linter exit ${result.status}`;
  }
  return "";
}

function parseReport(output) {
  try {
    return { report: JSON.parse(output) };
  } catch (error) {
    return { error: `design-md: FAIL | invalid JSON report: ${error.message}` };
  }
}

function reportError(report) {
  if (reportExitCode(report)) {
    return `design-md: FAIL | errors=${report.summary?.errors} warnings=${report.summary?.warnings}`;
  }
  return "";
}

const requestedDesignPath = () => path.resolve(process.argv[2] || "DESIGN.md");

function main() {
  const result = runLinter(requestedDesignPath());
  forwardOutput(result);
  const failure = executionError(result);
  if (failure) {
    console.error(failure);
    return 1;
  }
  const parsed = parseReport(result.stdout);
  if (parsed.error) {
    console.error(parsed.error);
    return 1;
  }
  const invalidReport = reportError(parsed.report);
  if (invalidReport) {
    console.error(invalidReport);
    return 1;
  }
  console.log("design-md: PASS");
  return 0;
}

module.exports = { reportExitCode };

if (require.main === module) process.exit(main());
