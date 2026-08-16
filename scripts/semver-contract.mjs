#!/usr/bin/env node

import semver from "semver";

function stableMajor(value, major) {
  const valid = semver.valid(value, { loose: false });
  if (valid === null) return false;
  const parsed = new semver.SemVer(valid);
  return parsed.major === major && parsed.prerelease.length === 0;
}

function rangeWithinMajor(value, major) {
  const source = value.startsWith("workspace:") ? value.slice("workspace:".length) : value;
  const valid = semver.validRange(source, { loose: false });
  if (valid === null) return false;
  if (/\d+\.\d+\.\d+-[0-9A-Za-z]/u.test(source)) return false;
  const allowed = `>=${major}.0.0 <${major + 1}.0.0`;
  return semver.intersects(source, allowed) && semver.subset(source, allowed);
}

function main() {
  const [mode, value, rawMajor] = process.argv.slice(2);
  const major = Number.parseInt(rawMajor ?? "", 10);
  if (!Number.isSafeInteger(major) || major < 0 || typeof value !== "string") return false;
  if (mode === "stable-major") return stableMajor(value, major);
  if (mode === "range-major") return rangeWithinMajor(value, major);
  return false;
}

process.exitCode = main() ? 0 : 1;
