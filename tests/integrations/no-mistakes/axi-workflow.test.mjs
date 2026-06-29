#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../../..', import.meta.url).pathname);
const text = fs.readFileSync(path.join(repo, 'integrations/no-mistakes/references/axi-workflow.md'), 'utf8');

assert.ok(text.includes('Proof-scanner review findings have a loop limit.'));
assert.ok(text.includes('Authorize at most one bounded'));
assert.ok(text.includes('report a design-loop/breadth issue instead of continuing auto-fix'));
assert.ok(text.includes('For package-manager scope findings, do not model workspace/fanout semantics in'));
assert.ok(text.includes('recursive/fanout flags, and equivalent package-manager env'));
assert.ok(text.includes('must fail closed unless a later owner adds explicit trusted resolution'));
assert.ok(text.includes('Before rerunning after any proof-scanner finding, do a local adversarial sweep'));
assert.ok(text.includes('Node preload/config paths such as `NODE_OPTIONS`'));
assert.ok(text.includes('Go execution'));
assert.ok(text.includes('URI-style path values such as `file://` and `data:`'));

console.log('no-mistakes axi workflow: pass');
