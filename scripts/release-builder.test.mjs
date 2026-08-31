import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  assertReleaseEligibility,
  buildRelease,
  classifyExistingRelease,
  createManifest,
  deriveReleaseVersion,
  expectedAssets,
  RELEASE_COMPATIBILITY,
  RELEASE_DISPATCH_ACTOR,
  RELEASE_DISPATCH_EVENT,
  RELEASE_SCHEMA_VERSION,
  ReleaseBuilderError,
  releaseAssetNames,
  releaseEligibility,
  validateAttestationReceipt,
  validateDraftReleaseIdentity,
  validateReleaseIdentity,
  validateTagReference,
} from "./release-builder.mjs";

const ROOT = path.resolve(new URL("..", import.meta.url).pathname);
const gitEnv = Object.fromEntries(
  Object.entries(process.env).filter(([name]) => !name.startsWith("GIT_")),
);
const HEAD = execFileSync("git", ["-C", ROOT, "rev-parse", "--verify", "HEAD"], {
  encoding: "utf8",
  env: gitEnv,
}).trim();
const OTHER_SHA = "b".repeat(40);

function digest(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function releaseFixture(expected, overrides = {}) {
  return {
    tag_name: expected.version,
    target_commitish: expected.source_commit,
    prerelease: true,
    draft: false,
    immutable: true,
    assets: expected.assets.map((asset) => ({
      ...asset,
      state: "uploaded",
      digest: `sha256:${asset.sha256}`,
    })),
    ...overrides,
  };
}

function expectedFixture() {
  return {
    version: deriveReleaseVersion(HEAD),
    source_commit: HEAD,
    assets: [
      { name: `${"hard-eng"}-${deriveReleaseVersion(HEAD)}.tar.gz`, sha256: "a".repeat(64) },
      { name: `${"hard-eng"}-${deriveReleaseVersion(HEAD)}.manifest.json`, sha256: "b".repeat(64) },
    ],
  };
}

test("derives a deterministic SHA-tagged prerelease without run metadata", () => {
  assert.equal(
    deriveReleaseVersion("a".repeat(40)),
    "v0.1.0-alpha.gaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  );
  for (const value of ["", "0", "a".repeat(39), "A".repeat(40), "a".repeat(41), null]) {
    assert.throws(() => deriveReleaseVersion(value), ReleaseBuilderError);
  }
});

test("accepts only main pushes or the exact release bot dispatch", () => {
  assert.deepEqual(releaseEligibility({ eventName: "push", ref: "refs/heads/main", sha: HEAD }), {
    eligible: true,
    reasons: [],
  });
  const dispatch = {
    eventName: "repository_dispatch",
    ref: "refs/heads/main",
    sha: OTHER_SHA,
    payloadSha: HEAD,
    mainSha: OTHER_SHA,
    payloadIsAncestor: true,
    action: RELEASE_DISPATCH_EVENT,
    actor: RELEASE_DISPATCH_ACTOR,
  };
  assert.equal(releaseEligibility(dispatch).eligible, true);
  assert.equal(assertReleaseEligibility(dispatch).sha, HEAD);
  for (const mutation of [
    { eventName: "pull_request", ref: "refs/heads/main", sha: HEAD },
    { eventName: "workflow_dispatch", ref: "refs/heads/main", sha: HEAD },
    { ...dispatch, action: "other-event" },
    { ...dispatch, actor: "octocat" },
    { ...dispatch, payloadSha: "c".repeat(40), payloadIsAncestor: false },
    { ...dispatch, ref: "refs/heads/release" },
  ]) {
    assert.equal(releaseEligibility(mutation).eligible, false);
    assert.throws(() => assertReleaseEligibility(mutation), /release is not eligible/);
  }
});

test("builds byte-identical archive and a manifest with only source identity", () => {
  const first = fs.mkdtempSync(path.join(os.tmpdir(), "hard-eng-release-test-"));
  const second = fs.mkdtempSync(path.join(os.tmpdir(), "hard-eng-release-test-"));
  try {
    const left = buildRelease({ root: ROOT, outputDir: first, commit: HEAD });
    const right = buildRelease({ root: ROOT, outputDir: second, commit: HEAD });
    assert.equal(fs.readFileSync(left.archive).equals(fs.readFileSync(right.archive)), true);
    assert.equal(fs.readFileSync(left.manifest).equals(fs.readFileSync(right.manifest)), true);
    const manifest = JSON.parse(fs.readFileSync(left.manifest, "utf8"));
    assert.deepEqual(manifest, {
      archive: {
        name: releaseAssetNames(left.version).archive,
        sha256: digest(left.archive),
        size: fs.statSync(left.archive).size,
      },
      compatibility: RELEASE_COMPATIBILITY,
      minimum_supported_version: `v0.1.0-alpha.g${"0".repeat(40)}`,
      product: "hard-eng",
      schema_version: RELEASE_SCHEMA_VERSION,
      source_commit: HEAD,
      version: `v0.1.0-alpha.g${HEAD}`,
    });
    assert.equal(Object.hasOwn(manifest, "workflow_run_number"), false);
  } finally {
    fs.rmSync(first, { recursive: true, force: true });
    fs.rmSync(second, { recursive: true, force: true });
  }
});

test("accepts exact immutable identity and rejects target, tag, asset, or mutable changes", () => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), "hard-eng-release-test-"));
  try {
    const built = buildRelease({ root: ROOT, outputDir: output, commit: HEAD });
    const expected = { version: built.version, source_commit: HEAD, assets: expectedAssets(built) };
    assert.equal(validateReleaseIdentity(releaseFixture(expected), expected), true);
    assert.throws(
      () =>
        validateReleaseIdentity(
          releaseFixture(expected, { target_commitish: OTHER_SHA }),
          expected,
        ),
      /target commit/,
    );
    assert.throws(
      () =>
        validateReleaseIdentity(
          releaseFixture(expected, { tag_name: deriveReleaseVersion(OTHER_SHA) }),
          expected,
        ),
      /tag does not match/,
    );
    assert.throws(
      () => validateReleaseIdentity(releaseFixture(expected, { immutable: false }), expected),
      /immutable/,
    );
    assert.throws(
      () => validateReleaseIdentity(releaseFixture(expected, { draft: true }), expected),
      /published/,
    );
    assert.throws(
      () =>
        validateReleaseIdentity(
          releaseFixture(expected, {
            assets: [
              { ...releaseFixture(expected).assets[0], digest: `sha256:${"0".repeat(64)}` },
              releaseFixture(expected).assets[1],
            ],
          }),
          expected,
        ),
      /digest does not match/,
    );
  } finally {
    fs.rmSync(output, { recursive: true, force: true });
  }
});

test("resumes only an exact draft with a subset of expected assets", () => {
  const expected = expectedFixture();
  assert.deepEqual(classifyExistingRelease(null, expected), {
    action: "create",
    missing_assets: expected.assets.map((asset) => asset.name),
  });
  const draft = releaseFixture(expected, {
    draft: true,
    immutable: false,
    assets: [
      {
        ...expected.assets[0],
        state: "uploaded",
        digest: `sha256:${expected.assets[0].sha256}`,
      },
    ],
  });
  assert.deepEqual(validateDraftReleaseIdentity(draft, expected), [expected.assets[1].name]);
  assert.deepEqual(classifyExistingRelease(draft, expected), {
    action: "resume",
    missing_assets: [expected.assets[1].name],
  });
  assert.deepEqual(classifyExistingRelease(releaseFixture(expected), expected), {
    action: "reuse",
    missing_assets: [],
  });
  assert.equal(
    classifyExistingRelease(
      {
        ...draft,
        assets: [
          ...draft.assets,
          { name: "unexpected", state: "uploaded", digest: `sha256:${"c".repeat(64)}` },
        ],
      },
      expected,
    ).action,
    "stop",
  );
  assert.equal(
    classifyExistingRelease({ ...draft, target_commitish: OTHER_SHA }, expected).action,
    "stop",
  );
});

test("claims an exact lightweight tag commit and stops on tag races", () => {
  const expected = expectedFixture();
  const tag = { ref: `refs/tags/${expected.version}`, object: { type: "commit", sha: HEAD } };
  assert.equal(validateTagReference(tag, expected), true);
  assert.throws(
    () => validateTagReference({ ...tag, object: { ...tag.object, sha: OTHER_SHA } }, expected),
    /tag commit/,
  );
  assert.throws(
    () =>
      validateTagReference(
        { ...tag, ref: `refs/tags/${deriveReleaseVersion(OTHER_SHA)}` },
        expected,
      ),
    /tag reference/,
  );
  assert.throws(
    () => validateTagReference({ ...tag, object: { type: "tag", sha: HEAD } }, expected),
    /directly to a commit/,
  );
});

test("requires a non-empty receipt from the cryptographic release verifier", () => {
  assert.equal(validateAttestationReceipt({ verified: true }), true);
  assert.throws(() => validateAttestationReceipt(null), /attestation/);
  assert.throws(() => validateAttestationReceipt({}), /attestation/);
  assert.throws(() => validateAttestationReceipt([]), /attestation/);
});

test("rejects a manifest identity that still includes run metadata", () => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), "hard-eng-release-test-"));
  try {
    const archive = path.join(output, `${"hard-eng"}-${deriveReleaseVersion(HEAD)}.tar.gz`);
    fs.writeFileSync(archive, "archive");
    const manifest = createManifest({
      version: deriveReleaseVersion(HEAD),
      commit: HEAD,
      archivePath: archive,
    });
    assert.equal(Object.hasOwn(manifest, "workflow_run_number"), false);
  } finally {
    fs.rmSync(output, { recursive: true, force: true });
  }
});
