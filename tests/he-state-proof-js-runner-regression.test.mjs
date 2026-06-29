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
  'jest --setupFilesAfterEnv=/tmp/exit0.js tests',
  'jest --testRunner=/tmp/runner.js tests',
  'jest --reporters=/tmp/reporter.js tests',
  'npx jest --setupFilesAfterEnv=/tmp/exit0.js tests',
  'npm exec jest --testRunner=/tmp/runner.js tests',
  'npm run jest -- --reporters=/tmp/reporter.js tests',
  'mocha --require=/tmp/exit0.js tests',
  'mocha --config file:///tmp/mocha.config.js tests',
  'mocha --node-option require=/tmp/exit0.js tests',
  'mocha --node-option "--require /tmp/exit0.js" tests',
  'mocha --node-option=import=file:///tmp/exit0.mjs tests',
  'mocha -n require=/tmp/exit0.js tests',
  'mocha --pass-on-failing-test-suite tests',
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
  'jest --setupFilesAfterEnv test/setup.js tests/owner.test.js',
  'jest --testRunner tools/jest-runner.js tests/owner.test.js',
  'jest --reporters reporters/owner.js tests/owner.test.js',
  'mocha --require test/setup.js tests/owner.test.js',
  'mocha --config test/mocha.config.js tests/owner.test.js',
  'mocha --node-option require=tools/register.js tests/owner.test.js',
  'mocha --node-option "--require tools/register.js" tests/owner.test.js',
  'ava --config test/ava.config.mjs test/owner.test.js',
  'tap --node-arg=--require=tools/tap-setup.js tests/owner.test.js',
]) {
  assert.equal(hasImplementationProofCommand(command, jsOptions), true, command);
  assert.equal(hasTestFirstProofCommand(command, jsOptions), true, command);
}

for (const testScript of [
  'node --test --help',
  'node --test || true',
  'node --test --import=file:///tmp/exit0.mjs',
]) {
  const options = { root: emptyRepo, packageScripts: { test: testScript } };
  assert.equal(hasImplementationProofCommand('node --test', options), false, testScript);
  assert.equal(hasTestFirstProofCommand('node --test', options), false, testScript);
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
