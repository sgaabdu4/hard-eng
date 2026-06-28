#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../../..', import.meta.url).pathname);
const text = fs.readFileSync(path.join(repo, 'integrations/no-mistakes/references/axi-workflow.md'), 'utf8');

assert.ok(text.includes('Proof-scanner review findings have a loop limit.'));
assert.ok(text.includes('Authorize at most one bounded'));
assert.ok(text.includes('report a design-loop/breadth issue instead of continuing auto-fix'));

console.log('no-mistakes axi workflow: pass');
