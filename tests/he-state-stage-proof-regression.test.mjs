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

const unsafeNodeInlineProof = state('he-implement');
unsafeNodeInlineProof.guardrails = unsafeNodeInlineProof.guardrails.map((guardrail) => (
  ['test-first-proof', 'implementation-proof'].includes(guardrail.id)
    ? { ...guardrail, command: 'node --test --eval=process.exit(0)' }
    : guardrail
));
result = run(unsafeNodeInlineProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const unsafeMochaInvertProof = state('he-implement');
unsafeMochaInvertProof.guardrails = unsafeMochaInvertProof.guardrails.map((guardrail) => (
  ['test-first-proof', 'implementation-proof'].includes(guardrail.id)
    ? { ...guardrail, command: 'mocha --invert --grep . tests' }
    : guardrail
));
result = run(unsafeMochaInvertProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-node-stack-'));
fs.writeFileSync(path.join(root, 'package.json'), `${JSON.stringify({ scripts: { test: 'npm run unit', unit: 'node --test src/owner.test.mjs' } }, null, 2)}\n`);

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

const passthroughRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-js-runner-'));
fs.writeFileSync(path.join(passthroughRoot, 'package.json'), `${JSON.stringify({ scripts: { test: 'npm run test:unit', 'test:unit': 'jest', 'make-it-fail': 'jest tests/make-it-fail.test.js' } }, null, 2)}\n`);

const unsafeNestedProof = state('he-implement');
unsafeNestedProof.guardrails = unsafeNestedProof.guardrails.map((guardrail) => (
  ['test-first-proof', 'implementation-proof'].includes(guardrail.id)
    ? { ...guardrail, command: 'npm test -- --setupFilesAfterEnv=/tmp/exit0.js' }
    : guardrail
));
const unsafeNestedFile = path.join(passthroughRoot, 'unsafe-nested.json');
fs.writeFileSync(unsafeNestedFile, `${JSON.stringify(unsafeNestedProof, null, 2)}\n`);
result = spawnSync('node', [script, 'validate', unsafeNestedFile], { encoding: 'utf8' });
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const unsafeMakeItFailProof = state('he-implement');
unsafeMakeItFailProof.guardrails = unsafeMakeItFailProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm run make-it-fail -- --setupFilesAfterEnv=/tmp/exit0.js', evidence: [tq('make-it-fail failed as expected before implementation')] }
    : guardrail
));
const unsafeMakeItFailFile = path.join(passthroughRoot, 'unsafe-make-it-fail.json');
fs.writeFileSync(unsafeMakeItFailFile, `${JSON.stringify(unsafeMakeItFailProof, null, 2)}\n`);
result = spawnSync('node', [script, 'validate', unsafeMakeItFailFile], { encoding: 'utf8' });
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

console.log('he-state-stage-proof-regression-test: pass');
