#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const version = fs.readFileSync(path.join(repo, 'VERSION'), 'utf8').trim();
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const product = fs.readFileSync(path.join(repo, 'PRODUCT.md'), 'utf8');
const versionTagWorkflow = fs.readFileSync(path.join(repo, '.github', 'workflows', 'version-tag.yml'), 'utf8');
const tag = `v${version}`;

assert.match(version, /^0\.\d+\.\d+-alpha\.\d+$/);
assert.ok(readme.includes('pre-1.0 and not version 1 yet'), 'README must state pre-1.0 maturity');
assert.ok(readme.includes(version), 'README must show VERSION value');
assert.ok(readme.includes(tag), 'README must show matching Git tag');
assert.ok(readme.includes('.github/workflows/version-tag.yml'), 'README must document the version tag workflow');
assert.ok(readme.includes('does not guess or bump versions'), 'README must state CI does not choose versions');
assert.ok(product.includes('pre-1.0 alpha'), 'PRODUCT must state maturity surface');
assert.ok(product.includes('[VERSION](VERSION)'), 'PRODUCT must name VERSION as release string owner');
assert.match(versionTagWorkflow, /name:\s*version-tag/);
assert.match(versionTagWorkflow, /push:\s*\n\s*branches:\s*\n\s*-\s*main/);
assert.match(versionTagWorkflow, /paths:\s*\n\s*-\s*VERSION/);
assert.match(versionTagWorkflow, /contents:\s*write/);
assert.ok(versionTagWorkflow.includes('^0\\.[0-9]+\\.[0-9]+-alpha\\.[0-9]+$'), 'tag workflow must enforce alpha versions');
assert.ok(versionTagWorkflow.includes('tag="v${version}"'), 'tag workflow must derive tag from VERSION');
assert.ok(versionTagWorkflow.includes('git ls-remote --exit-code --tags origin "refs/tags/${tag}"'), 'tag workflow must be idempotent');
assert.ok(versionTagWorkflow.includes('git tag -a "$tag"'), 'tag workflow must create an annotated tag');
assert.ok(versionTagWorkflow.includes('git push origin "refs/tags/${tag}"'), 'tag workflow must push only the tag ref');

console.log('versioning-contract-test: pass');
