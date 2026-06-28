#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const version = fs.readFileSync(path.join(repo, 'VERSION'), 'utf8').trim();
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const product = fs.readFileSync(path.join(repo, 'PRODUCT.md'), 'utf8');
const versionTagWorkflow = fs.readFileSync(path.join(repo, '.github', 'workflows', 'version-tag.yml'), 'utf8');
const prVersionBumpWorkflow = fs.readFileSync(path.join(repo, '.github', 'workflows', 'pr-version-bump.yml'), 'utf8');
const tag = `v${version}`;

assert.match(version, /^0\.\d+\.\d+-alpha\.\d+$/);
assert.ok(readme.includes('pre-1.0 and not version 1 yet'), 'README must state pre-1.0 maturity');
assert.ok(readme.includes(version), 'README must show VERSION value');
assert.ok(readme.includes(tag), 'README must show matching Git tag');
assert.ok(readme.includes('.github/workflows/version-tag.yml'), 'README must document the version tag workflow');
assert.ok(readme.includes('.github/workflows/pr-version-bump.yml'), 'README must document the PR version bump workflow');
assert.ok(readme.includes('does not guess or bump versions'), 'README must state CI does not choose versions');
assert.ok(product.includes('pre-1.0 alpha'), 'PRODUCT must state maturity surface');
assert.ok(product.includes('[VERSION](VERSION)'), 'PRODUCT must name VERSION as release string owner');
assert.ok(product.includes('red-first or mutation `test-first-proof` before `owner-change`'), 'PRODUCT must document Implement proof gate');
assert.ok(product.includes('open learning or process findings route to `/he:learn`'), 'PRODUCT must document learning gate');
assert.match(versionTagWorkflow, /name:\s*version-tag/);
assert.match(versionTagWorkflow, /push:\s*\n\s*branches:\s*\n\s*-\s*main/);
assert.match(versionTagWorkflow, /paths:\s*\n\s*-\s*VERSION/);
assert.match(versionTagWorkflow, /contents:\s*write/);
assert.ok(versionTagWorkflow.includes('^0\\.[0-9]+\\.[0-9]+-alpha\\.[0-9]+$'), 'tag workflow must enforce alpha versions');
assert.ok(versionTagWorkflow.includes('tag="v${version}"'), 'tag workflow must derive tag from VERSION');
assert.ok(versionTagWorkflow.includes('git ls-remote --exit-code --tags origin "refs/tags/${tag}"'), 'tag workflow must be idempotent');
assert.ok(versionTagWorkflow.includes('refusing to reuse it'), 'tag workflow must reject reused version tags');
assert.ok(versionTagWorkflow.includes('git tag -a "$tag"'), 'tag workflow must create an annotated tag');
assert.ok(versionTagWorkflow.includes('git push origin "refs/tags/${tag}"'), 'tag workflow must push only the tag ref');
assert.match(prVersionBumpWorkflow, /name:\s*pr-version-bump/);
assert.match(prVersionBumpWorkflow, /pull_request_target:/);
assert.ok(prVersionBumpWorkflow.includes('github.event.pull_request.head.repo.full_name == github.repository'), 'PR bump workflow must only write same-repo PR branches');
assert.match(prVersionBumpWorkflow, /contents:\s*write/);
assert.ok(prVersionBumpWorkflow.includes('base_version="$(git show "origin/${BASE_REF}:VERSION"'), 'PR bump workflow must derive from base VERSION');
assert.ok(prVersionBumpWorkflow.includes('^0\\.([0-9]+)\\.([0-9]+)-alpha\\.([0-9]+)$'), 'PR bump workflow must enforce alpha versions');
assert.ok(prVersionBumpWorkflow.includes('next_alpha=$((base_alpha + 1))'), 'PR bump workflow must increment alpha from base');
assert.ok(prVersionBumpWorkflow.includes('if (( PR_NUMBER > next_alpha ))'), 'PR bump workflow must use PR number as a uniqueness floor');
assert.ok(prVersionBumpWorkflow.includes('printf'), 'PR bump workflow must write VERSION');
assert.ok(prVersionBumpWorkflow.includes('README.md'), 'PR bump workflow must keep README in sync');
assert.ok(prVersionBumpWorkflow.includes('git diff --quiet -- VERSION README.md'), 'PR bump workflow must avoid commit loops');
assert.ok(prVersionBumpWorkflow.includes('git commit -m "Bump alpha version for PR #${PR_NUMBER}"'), 'PR bump workflow must commit the bump');
assert.ok(prVersionBumpWorkflow.includes('git push origin "HEAD:${HEAD_REF}"'), 'PR bump workflow must push back to the PR branch');

console.log('versioning-contract-test: pass');
