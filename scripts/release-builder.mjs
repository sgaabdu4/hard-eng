#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const RELEASE_BASE_VERSION = "0.1.0";
export const RELEASE_ZERO_SHA = "0".repeat(40);
export const MINIMUM_SUPPORTED_VERSION = `v${RELEASE_BASE_VERSION}-alpha.g${RELEASE_ZERO_SHA}`;
export const RELEASE_SCHEMA_VERSION = 2;
export const RELEASE_PRODUCT = "hard-eng";
export const RELEASE_DISPATCH_EVENT = "hard-eng-release";
export const RELEASE_DISPATCH_ACTOR = "github-actions[bot]";
export const RELEASE_COMPATIBILITY = Object.freeze({
  agents: Object.freeze(["claude", "codex", "copilot"]),
  node: ">=26.0.0",
  platforms: Object.freeze([
    "linux-x64",
    "linux-arm64",
    "darwin-x64",
    "darwin-arm64",
    "windows-x64",
  ]),
});

const SHA256 = /^[0-9a-f]{64}$/u;
const COMMIT = /^[0-9a-f]{40}$/u;
const VERSION = new RegExp(
  `^v${RELEASE_BASE_VERSION.replaceAll(".", "\\.")}-alpha\\.g${COMMIT.source.slice(1, -1)}$`,
  "u",
);
const gitEnv = Object.fromEntries(
  Object.entries(process.env).filter(([name]) => !name.startsWith("GIT_")),
);

export class ReleaseBuilderError extends Error {}

function fail(message) {
  throw new ReleaseBuilderError(message);
}

function requireCondition(condition, message) {
  if (!condition) fail(message);
}

function assertString(value, message) {
  if (typeof value !== "string" || value.length === 0) fail(message);
  return value;
}

function assertCommit(commit) {
  const value = assertString(commit, "source commit is required");
  if (!COMMIT.test(value)) fail("source commit must be a 40-character lowercase SHA-1");
  return value;
}

function assertVersion(version) {
  const value = assertString(version, "release version is required");
  if (!VERSION.test(value)) fail("release version must contain the exact source SHA");
  return value;
}

function assertSha256(value, label) {
  if (typeof value !== "string" || !SHA256.test(value))
    fail(`${label} must be a lowercase SHA-256 digest`);
  return value;
}

function validCommit(value) {
  return typeof value === "string" && COMMIT.test(value);
}

function fileDigest(file) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(file));
  return hash.digest("hex");
}

function fileSize(file) {
  const stats = fs.statSync(file, { bigint: false });
  if (!stats.isFile()) fail(`release asset is not a regular file: ${file}`);
  return stats.size;
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value).sort(([left], [right]) =>
      left < right ? -1 : left > right ? 1 : 0,
    );
    return `{${entries.map(([key, entry]) => `${JSON.stringify(key)}:${stableJson(entry)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function safePath(value, label) {
  const resolved = path.resolve(assertString(value, `${label} is required`));
  if (resolved === path.parse(resolved).root) fail(`${label} cannot be the filesystem root`);
  return resolved;
}

function runGitArchive(root, commit, archive) {
  const prefix = `${path.basename(archive, ".tar.gz")}/`;
  execFileSync(
    "git",
    ["-C", root, "archive", "--format=tar.gz", `--prefix=${prefix}`, "--output", archive, commit],
    { env: gitEnv, stdio: ["ignore", "ignore", "pipe"] },
  );
}

function checkedCommit(root, commit) {
  let resolved;
  try {
    resolved = execFileSync("git", ["-C", root, "rev-parse", "--verify", `${commit}^{commit}`], {
      encoding: "utf8",
      env: gitEnv,
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch {
    fail(`source commit is not present in the checkout: ${commit}`);
  }
  if (resolved !== commit) fail(`source commit resolved unexpectedly: ${resolved}`);
}

export function deriveReleaseVersion(commit) {
  return `v${RELEASE_BASE_VERSION}-alpha.g${assertCommit(commit)}`;
}

function validDispatchHashes(payloadSha, mainSha) {
  if (!validCommit(payloadSha)) return false;
  return validCommit(mainSha);
}

function ancestorFlag(value) {
  return value === true || value === "true";
}

function dispatchRelationIsValid({ payloadSha, mainSha, payloadIsAncestor }) {
  if (!validDispatchHashes(payloadSha, mainSha)) return false;
  if (payloadSha === mainSha) return true;
  return ancestorFlag(payloadIsAncestor);
}

function sourceShaFor(input) {
  return input.eventName === "repository_dispatch" ? input.payloadSha : input.sha;
}

function baseEligibilityChecks(input, sourceSha) {
  return [
    {
      valid: ["push", "repository_dispatch"].includes(input.eventName),
      reason: "event is not a trusted push or bot dispatch",
    },
    { valid: input.ref === "refs/heads/main", reason: "ref is not refs/heads/main" },
    {
      valid: validCommit(sourceSha),
      reason: "source commit must be a 40-character lowercase SHA-1",
    },
  ];
}

function dispatchEligibilityChecks(input) {
  if (input.eventName !== "repository_dispatch") return [];
  const mainSha = input.mainSha ?? input.sha;
  return [
    {
      valid: input.action === RELEASE_DISPATCH_EVENT,
      reason: "dispatch event type is not approved",
    },
    {
      valid: input.actor === RELEASE_DISPATCH_ACTOR,
      reason: "dispatch actor is not the release bot",
    },
    {
      valid: dispatchRelationIsValid({
        payloadSha: input.payloadSha,
        mainSha,
        payloadIsAncestor: input.payloadIsAncestor,
      }),
      reason: "dispatch source must be the current main commit or its ancestor",
    },
  ];
}

export function releaseEligibility(input = {}) {
  const sourceSha = sourceShaFor(input);
  const checks = [...baseEligibilityChecks(input, sourceSha), ...dispatchEligibilityChecks(input)];
  const reasons = checks.filter((check) => !check.valid).map((check) => check.reason);
  return { eligible: reasons.length === 0, reasons };
}

export function assertReleaseEligibility(input = {}) {
  const result = releaseEligibility(input);
  if (!result.eligible) fail(`release is not eligible: ${result.reasons.join("; ")}`);
  const sourceSha = input.eventName === "repository_dispatch" ? input.payloadSha : input.sha;
  const sha = assertCommit(sourceSha);
  return { eventName: input.eventName, ref: input.ref, sha, version: deriveReleaseVersion(sha) };
}

export function releaseAssetNames(version) {
  const tag = assertVersion(version);
  return {
    archive: `${RELEASE_PRODUCT}-${tag}.tar.gz`,
    manifest: `${RELEASE_PRODUCT}-${tag}.manifest.json`,
  };
}

export function createManifest({ version, commit, archivePath }) {
  const sourceCommit = assertCommit(commit);
  const tag = assertVersion(version);
  requireCondition(
    tag === deriveReleaseVersion(sourceCommit),
    "release version must contain the source SHA",
  );
  const archive = safePath(archivePath, "archive path");
  const names = releaseAssetNames(tag);
  requireCondition(
    path.basename(archive) === names.archive,
    `archive path must be named ${names.archive}`,
  );
  return {
    archive: { name: names.archive, sha256: fileDigest(archive), size: fileSize(archive) },
    compatibility: RELEASE_COMPATIBILITY,
    minimum_supported_version: MINIMUM_SUPPORTED_VERSION,
    product: RELEASE_PRODUCT,
    schema_version: RELEASE_SCHEMA_VERSION,
    source_commit: sourceCommit,
    version: tag,
  };
}

export function writeManifest(file, manifest) {
  const target = safePath(file, "manifest path");
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${stableJson(manifest)}\n`, {
    encoding: "utf8",
    mode: 0o644,
    flag: "w",
  });
  return target;
}

export function buildRelease({ root = process.cwd(), outputDir, commit }) {
  const checkout = safePath(root, "repository root");
  const output = safePath(
    outputDir ?? fs.mkdtempSync(path.join(os.tmpdir(), "hard-eng-release-")),
    "release output directory",
  );
  fs.mkdirSync(output, { recursive: true });
  const sourceCommit = assertCommit(commit);
  checkedCommit(checkout, sourceCommit);
  const version = deriveReleaseVersion(sourceCommit);
  const names = releaseAssetNames(version);
  const archive = path.join(output, names.archive);
  const manifestPath = path.join(output, names.manifest);
  runGitArchive(checkout, sourceCommit, archive);
  writeManifest(
    manifestPath,
    createManifest({ version, commit: sourceCommit, archivePath: archive }),
  );
  return {
    archive,
    archive_sha256: fileDigest(archive),
    assets: expectedAssets({ archive, manifest: manifestPath }),
    manifest: manifestPath,
    manifest_sha256: fileDigest(manifestPath),
    source_commit: sourceCommit,
    version,
  };
}

function releaseAssets(release) {
  requireCondition(Array.isArray(release?.assets), "release assets are missing");
  return release.assets;
}

function assertExpectedAssetList(assets) {
  if (!Array.isArray(assets)) fail("expected release assets are missing");
  if (assets.length === 0) fail("expected release assets are missing");
}

function expectedAssetEntry(asset) {
  if (asset == null || typeof asset !== "object") fail("expected release asset is invalid");
  const name = assertString(asset.name, "expected asset name is missing");
  const digest = assertSha256(asset.sha256, `expected asset ${name} digest`);
  return { name, digest };
}

function expectedAssetMap(expected) {
  const assets = expected?.assets;
  assertExpectedAssetList(assets);
  const map = new Map();
  for (const asset of assets) {
    const entry = expectedAssetEntry(asset);
    if (map.has(entry.name)) fail(`duplicate expected asset: ${entry.name}`);
    map.set(entry.name, entry.digest);
  }
  return map;
}

function assertExpectedIdentity(expected) {
  requireCondition(
    expected != null && typeof expected === "object" && !Array.isArray(expected),
    "expected release identity is missing",
  );
  const sourceCommit = assertCommit(expected.source_commit);
  const version = assertVersion(expected.version);
  requireCondition(
    version === deriveReleaseVersion(sourceCommit),
    "expected release version does not contain the source SHA",
  );
  return { sourceCommit, version };
}

function validateReleaseCommon(release, expected) {
  requireCondition(
    release != null && typeof release === "object" && !Array.isArray(release),
    "release response is missing",
  );
  const identity = assertExpectedIdentity(expected);
  requireCondition(
    release.tag_name === identity.version,
    "release tag does not match the source SHA",
  );
  requireCondition(
    release.target_commitish === identity.sourceCommit,
    "release target commit does not match the source SHA",
  );
  requireCondition(release.prerelease === true, "release must be a prerelease");
  return identity;
}

function validateAssetSubset(release, expected) {
  const expectedMap = expectedAssetMap(expected);
  const seen = new Set();
  for (const asset of releaseAssets(release)) {
    const name = assertString(asset?.name, "release asset name is missing");
    requireCondition(!seen.has(name), `release contains a duplicate asset: ${name}`);
    requireCondition(expectedMap.has(name), `release contains an unexpected asset: ${name}`);
    requireCondition(asset.state === "uploaded", `release asset is not uploaded: ${name}`);
    const digest = assertString(asset.digest, `release asset digest is missing: ${name}`);
    requireCondition(
      digest === `sha256:${expectedMap.get(name)}`,
      `release asset digest does not match: ${name}`,
    );
    seen.add(name);
  }
  return [...expectedMap.keys()].filter((name) => !seen.has(name));
}

export function validateReleaseIdentity(release, expected) {
  validateReleaseCommon(release, expected);
  requireCondition(release.draft === false, "release must be published, not a draft");
  requireCondition(release.immutable === true, "release is not immutable");
  const missing = validateAssetSubset(release, expected);
  requireCondition(
    missing.length === 0,
    "release asset set does not exactly match the built assets",
  );
  return true;
}

export function validateDraftReleaseIdentity(release, expected) {
  validateReleaseCommon(release, expected);
  requireCondition(release.draft === true, "release must be a draft to resume");
  requireCondition(release.immutable !== true, "draft release cannot already be immutable");
  return validateAssetSubset(release, expected);
}

export function validateTagReference(tag, expected) {
  const identity = assertExpectedIdentity(expected);
  requireCondition(
    tag != null && typeof tag === "object" && !Array.isArray(tag),
    "tag response is missing",
  );
  requireCondition(
    tag.ref === `refs/tags/${identity.version}`,
    "tag reference does not match the release version",
  );
  requireCondition(tag.object?.type === "commit", "tag must point directly to a commit");
  requireCondition(
    tag.object.sha === identity.sourceCommit,
    "tag commit does not match the source SHA",
  );
  return true;
}

export function expectedAssets({ archive, manifest }) {
  const archivePath = safePath(archive, "archive path");
  const manifestPath = safePath(manifest, "manifest path");
  return [
    { name: path.basename(archivePath), sha256: fileDigest(archivePath) },
    { name: path.basename(manifestPath), sha256: fileDigest(manifestPath) },
  ];
}

export function validateAttestationReceipt(receipt) {
  requireCondition(
    receipt != null && typeof receipt === "object",
    "release attestation receipt is missing",
  );
  const entries = Array.isArray(receipt) ? receipt.length : Object.keys(receipt).length;
  requireCondition(entries > 0, "release attestation receipt is empty");
  return true;
}

function errorMessage(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

function classifyImmutableRelease(release, expected) {
  try {
    validateReleaseIdentity(release, expected);
    return { action: "reuse", missing_assets: [] };
  } catch (error) {
    return { action: "invalid", reason: errorMessage(error, "existing release identity mismatch") };
  }
}

function classifyDraftRelease(release, expected, immutableReason) {
  try {
    const missing = validateDraftReleaseIdentity(release, expected);
    return { action: "resume", missing_assets: missing };
  } catch (error) {
    const reason = release.draft === true ? errorMessage(error, immutableReason) : immutableReason;
    return { action: "stop", reason };
  }
}

export function classifyExistingRelease(release, expected) {
  if (release == null) {
    return { action: "create", missing_assets: [...expectedAssetMap(expected).keys()] };
  }
  const immutable = classifyImmutableRelease(release, expected);
  if (immutable.action === "reuse") return immutable;
  return classifyDraftRelease(release, expected, immutable.reason);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      requireCondition(args.command === undefined, `unexpected argument: ${token}`);
      args.command = token;
      continue;
    }
    const key = token.slice(2).replaceAll("-", "_");
    const value = argv[index + 1];
    requireCondition(value !== undefined && !value.startsWith("--"), `missing value for --${key}`);
    args[key] = value;
    index += 1;
  }
  return args;
}

function readJsonFile(file, label) {
  const source = safePath(file, label);
  try {
    return JSON.parse(fs.readFileSync(source, "utf8"));
  } catch (error) {
    fail(`${label} is not valid JSON: ${errorMessage(error, "read failed")}`);
  }
}

function validateCheckedOutSha(args, sourceSha) {
  if (args.checked_out_sha !== undefined)
    requireCondition(
      args.checked_out_sha === sourceSha,
      "checked-out commit does not match the release source SHA",
    );
}

function eventCommand(args) {
  const eligibility = assertReleaseEligibility({
    eventName: args.event,
    ref: args.ref,
    sha: args.sha,
    action: args.action,
    actor: args.actor,
    payloadSha: args.payload_sha,
    mainSha: args.main_sha,
    payloadIsAncestor: args.payload_is_ancestor,
  });
  validateCheckedOutSha(args, eligibility.sha);
  process.stdout.write(`source_sha=${eligibility.sha}\nversion=${eligibility.version}\n`);
}

function versionCommand(args) {
  process.stdout.write(`${deriveReleaseVersion(args.commit)}\n`);
}

function buildCommand(args) {
  process.stdout.write(
    `${JSON.stringify(buildRelease({ root: args.root, outputDir: args.output, commit: args.commit }))}\n`,
  );
}

function classifyCommand(args) {
  const result = classifyExistingRelease(
    readJsonFile(args.release, "existing release response"),
    readJsonFile(args.expected, "expected release identity"),
  );
  requireCondition(result.action !== "stop", `existing release conflict: ${result.reason}`);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

function validateTagCommand(args) {
  validateTagReference(
    readJsonFile(args.tag, "tag response"),
    readJsonFile(args.expected, "expected release identity"),
  );
  process.stdout.write("release-builder: PASS tag=exact-source-commit\n");
}

function verifyDraftCommand(args) {
  const missing = validateDraftReleaseIdentity(
    readJsonFile(args.release, "draft release response"),
    readJsonFile(args.expected, "expected release identity"),
  );
  requireCondition(missing.length === 0, "draft release is missing assets before publish");
  process.stdout.write("release-builder: PASS draft=exact-assets\n");
}

function verifyCommand(args) {
  validateReleaseIdentity(
    readJsonFile(args.release, "release response"),
    readJsonFile(args.expected, "expected release identity"),
  );
  requireCondition(args.attestation !== undefined, "release attestation receipt is required");
  validateAttestationReceipt(readJsonFile(args.attestation, "release attestation receipt"));
  process.stdout.write("release-builder: PASS identity=immutable-assets-attestation\n");
}

const COMMANDS = Object.freeze({
  build: buildCommand,
  classify: classifyCommand,
  "validate-event": eventCommand,
  "validate-tag": validateTagCommand,
  verify: verifyCommand,
  "verify-draft": verifyDraftCommand,
  version: versionCommand,
});

function cli() {
  const args = parseArgs(process.argv.slice(2));
  const command = COMMANDS[args.command];
  requireCondition(
    typeof command === "function",
    "usage: release-builder.mjs validate-event ... | version --commit SHA | build --commit SHA --output DIR [--root DIR] | classify --release JSON --expected JSON | validate-tag --tag JSON --expected JSON | verify-draft --release JSON --expected JSON | verify --release JSON --expected JSON --attestation JSON",
  );
  command(args);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    cli();
  } catch (error) {
    process.stderr.write(
      `release-builder: FAIL: ${errorMessage(error, "release builder failed")}\n`,
    );
    process.exitCode = 1;
  }
}
