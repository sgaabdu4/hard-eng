import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-ssot-guardrails.mjs');

function makeRepo() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssot-guardrails-'));
  fs.mkdirSync(path.join(tmp, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(tmp, 'docs', 'design'), { recursive: true });
  fs.writeFileSync(path.join(tmp, 'scripts', 'check-one.mjs'), 'console.log("ok");\n');
  fs.writeFileSync(path.join(tmp, 'docs', 'design', 'tokens.css'), ':root { --ink: oklch(18% 0.02 250); }\n');
  fs.writeFileSync(path.join(tmp, 'README.md'), '# Test\n');
  fs.writeFileSync(path.join(tmp, 'PRODUCT.md'), '# Product\n');
  fs.writeFileSync(path.join(tmp, 'DESIGN.md'), '# Design\n');
  fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({
    scannerRegistry: [{ path: 'scripts/check-one.mjs', owners: ['ssot-guardrails.json'] }],
    patternRules: [{
      id: 'doc-colors',
      pattern: 'oklch\\(',
      include: ['docs/**/*.html', 'README.md', 'PRODUCT.md', 'DESIGN.md'],
      owners: ['docs/design/tokens.css'],
      message: 'color literals must use tokens',
    }],
  }, null, 2)}\n`);
  return tmp;
}

function run(root) {
  return spawnSync('node', [script, root], { encoding: 'utf8' });
}

let tmp = makeRepo();
let result = run(tmp);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /ssot-guardrails: pass/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'scripts', 'check-new-policy.mjs'), 'console.log("new");\n');
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /not registered in ssot-guardrails\.json/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'docs', 'bad.html'), '<style>body{color:oklch(12% 0.01 20)}</style>\n');
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /color literals must use tokens/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), '{ bad json');
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /invalid JSON/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({ patternRules: [] }, null, 2)}\n`);
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must define scannerRegistry/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({
  scannerRegistry: [{ path: 'scripts/check-one.mjs', owners: [] }],
  patternRules: [],
}, null, 2)}\n`);
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /owners must be non-empty/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({
  scannerRegistry: [{ path: 'scripts/check-missing.mjs', owners: ['ssot-guardrails.json'] }],
  patternRules: [],
}, null, 2)}\n`);
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /registered but missing/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({
  scannerRegistry: [{ path: 'scripts/check-one.mjs', owners: ['missing-owner.md'] }],
  patternRules: [],
}, null, 2)}\n`);
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /owner missing-owner\.md is missing/);

tmp = makeRepo();
fs.writeFileSync(path.join(tmp, 'ssot-guardrails.json'), `${JSON.stringify({
  scannerRegistry: [{ path: 'scripts/check-one.mjs', owners: ['ssot-guardrails.json'] }],
  patternRules: [{
    id: 'bad-regex',
    pattern: '[',
    include: ['README.md'],
    owners: ['docs/design/tokens.css'],
  }],
}, null, 2)}\n`);
result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /pattern is invalid/);

console.log('ssot-guardrails-test: pass');
