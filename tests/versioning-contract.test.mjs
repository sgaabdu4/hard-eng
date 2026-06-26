#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const version = fs.readFileSync(path.join(repo, 'VERSION'), 'utf8').trim();
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const product = fs.readFileSync(path.join(repo, 'PRODUCT.md'), 'utf8');
const tag = `v${version}`;

assert.match(version, /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/);
assert.ok(readme.includes('pre-1.0 and not version 1 yet'), 'README must state pre-1.0 maturity');
assert.ok(readme.includes(version), 'README must show VERSION value');
assert.ok(readme.includes(tag), 'README must show matching Git tag');
assert.ok(product.includes('pre-1.0 alpha'), 'PRODUCT must state maturity surface');
assert.ok(product.includes('[VERSION](VERSION)'), 'PRODUCT must name VERSION as release string owner');

console.log('versioning-contract-test: pass');
