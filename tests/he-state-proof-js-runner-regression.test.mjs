#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  hasImplementationProofCommand,
  hasTestFirstProofCommand,
} from '../scripts/he-state-proof.mjs';
import { emptyRepo } from './helpers/he-proof-options.mjs';

const jsOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: {} };

for (const command of [
  'mocha --require=/tmp/exit0.js tests',
  'mocha --config file:///tmp/mocha.config.js tests',
  'mocha --grep=^$ tests',
  'mocha /tmp/fake.test.js',
  'ava --config /tmp/ava.config.mjs',
  'ava --match=^$',
  'ava /tmp/fake.test.js',
  'tap --node-arg=--require=/tmp/exit0.js tests',
  'tap --test-regex=^$ tests',
  'tap /tmp/fake.test.js',
]) {
  assert.equal(hasImplementationProofCommand(command, jsOptions), false, command);
  assert.equal(hasTestFirstProofCommand(command, jsOptions), false, command);
}

for (const command of [
  'mocha --require test/setup.js tests/owner.test.js',
  'mocha --config test/mocha.config.js tests/owner.test.js',
  'ava --config test/ava.config.mjs test/owner.test.js',
  'tap --node-arg=--require=tools/tap-setup.js tests/owner.test.js',
]) {
  assert.equal(hasImplementationProofCommand(command, jsOptions), true, command);
  assert.equal(hasTestFirstProofCommand(command, jsOptions), true, command);
}

for (const testScript of [
  'node --test test/owner.test.mjs',
  'node --test tests/unit/owner.test.mjs',
]) {
  const options = { root: emptyRepo, packageScripts: { test: testScript } };
  assert.equal(hasImplementationProofCommand('npm test', options), true, testScript);
  assert.equal(hasTestFirstProofCommand('npm test', options), true, testScript);
}

for (const testPath of [
  ['test', 'owner.test.mjs'],
  ['tests', 'unit', 'owner.test.mjs'],
]) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-proof-node-stack-'));
  const file = path.join(repo, ...testPath);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, 'import "node:test";\n');
  assert.equal(hasImplementationProofCommand('node --test', { root: repo }), true, testPath.join('/'));
  assert.equal(hasTestFirstProofCommand('node --test', { root: repo }), true, testPath.join('/'));
}

console.log('he-state-proof-js-runner-regression-test: pass');
