#!/usr/bin/env node
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { run, state, tq } from './helpers/he-state-stage-fixture.mjs';

const unsafeDirectRunnerProof = state('he-implement');
unsafeDirectRunnerProof.guardrails = unsafeDirectRunnerProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'mocha --require=/tmp/exit0.js tests', evidence: [tq('red-first failed as expected before owner-change')] }
    : guardrail
));
let result = run(unsafeDirectRunnerProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-node-stack-'));
fs.writeFileSync(path.join(root, 'package.json'), `${JSON.stringify({ scripts: { test: 'node --test test/owner.test.mjs' } }, null, 2)}\n`);

const nodeScriptProof = state('he-implement');
nodeScriptProof.guardrails = nodeScriptProof.guardrails.map((guardrail) => (
  ['test-first-proof', 'implementation-proof'].includes(guardrail.id)
    ? { ...guardrail, command: 'npm test' }
    : guardrail
));
const stateFile = path.join(root, 'he-state.json');
fs.writeFileSync(stateFile, `${JSON.stringify(nodeScriptProof, null, 2)}\n`);
result = spawnSync('node', [script, 'validate', stateFile], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);

console.log('he-state-stage-proof-regression-test: pass');
