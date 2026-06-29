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
  'jest --globalSetup=/tmp/exit0.js tests',
  'jest --globalTeardown=/tmp/x.js tests',
  'jest --testEnvironment=/tmp/env.js tests',
  'jest --unknown=/tmp/exit0.js tests',
  'jest --unknown=../setup.js tests',
  'jest --unknown=file:///tmp/x.js tests',
  'jest --unknown=data:text/javascript,0 tests',
  'vitest --setupFiles=/tmp/setup.ts tests',
  'npx jest --setupFilesAfterEnv=/tmp/exit0.js tests',
  'npx vitest --setupFiles=/tmp/setup.ts tests',
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

const jestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'jest' } };
const vitestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'vitest' } };
const compoundJestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'echo setup && jest' } };

for (const command of [
  'npm test -- --setupFilesAfterEnv=/tmp/exit0.js',
  'npm test -- --reporters=/tmp/reporter.js',
  'npm test -- --globalSetup=/tmp/exit0.js',
  'npm test -- --globalTeardown=/tmp/x.js',
  'npm test -- --testEnvironment=/tmp/env.js',
  'npm test -- --unknown=file:///tmp/x.js',
]) {
  assert.equal(hasImplementationProofCommand(command, jestPackageOptions), false, command);
  assert.equal(hasTestFirstProofCommand(command, jestPackageOptions), false, command);
}

assert.equal(hasImplementationProofCommand('npm test -- --setupFiles=/tmp/setup.ts', vitestPackageOptions), false);
assert.equal(hasTestFirstProofCommand('npm test -- --setupFiles=/tmp/setup.ts', vitestPackageOptions), false);

for (const command of [
  'npm test -- --globalSetup=/tmp/exit0.js',
  'npm test -- --unknown=file:///tmp/x.js',
]) {
  assert.equal(hasImplementationProofCommand(command, compoundJestPackageOptions), false, command);
  assert.equal(hasTestFirstProofCommand(command, compoundJestPackageOptions), false, command);
}

for (const command of [
  'jest --setupFilesAfterEnv test/setup.js tests/owner.test.js',
  'jest --testRunner tools/jest-runner.js tests/owner.test.js',
  'jest --reporters reporters/owner.js tests/owner.test.js',
  'jest --globalSetup test/global.js tests/owner.test.js',
  'jest --globalTeardown test/global.js tests/owner.test.js',
  'jest --testEnvironment jest-environment-jsdom tests/owner.test.js',
  'vitest --setupFiles test/setup.ts tests/owner.test.ts',
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

for (const command of [
  'npm test -- --setupFilesAfterEnv test/setup.js tests/owner.test.js',
  'npm test -- --globalSetup test/global.js',
  'npm test -- --testEnvironment jest-environment-jsdom',
  'npm test -- --unknown=local-value',
]) {
  assert.equal(hasImplementationProofCommand(command, jestPackageOptions), true, command);
  assert.equal(hasTestFirstProofCommand(command, jestPackageOptions), true, command);
}

assert.equal(hasImplementationProofCommand('npm test -- --setupFiles test/setup.ts', vitestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test -- --setupFiles test/setup.ts', vitestPackageOptions), true);

assert.equal(hasImplementationProofCommand('npm test -- --globalSetup test/global.js', compoundJestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test -- --globalSetup test/global.js', compoundJestPackageOptions), true);

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
