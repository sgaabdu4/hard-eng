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
const nodeOptions = { root: emptyRepo, proofStacks: ['js-package', 'node'], packageScripts: { test: 'node --test tests/owner.test.mjs' } };

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

for (const command of [
  'node --test --test-reporter=/tmp/exit0.js',
  'node --test --test-reporter file:///tmp/x.mjs',
  'npm test -- --test-reporter=/tmp/exit0.js',
  'npm test -- --test-reporter file:///tmp/x.mjs',
  'node --test --test-global-setup=/tmp/exit0.js',
  'npm test -- --test-global-setup=/tmp/exit0.js',
  'node --test --eval=process.exit(0)',
  'node --test --eval process.exit(0)',
  'node --test -e process.exit(0)',
  'node --test -eprocess.exit(0)',
  'node --test --print=process.version',
  'node --test -p process.version',
  'node --test --check tests/owner.test.mjs',
  'node --test -c tests/owner.test.mjs',
  'npm test -- --eval=process.exit(0)',
  'npm test -- -e process.exit(0)',
  'npm test -- --print=process.version',
  'npm test -- --check tests/owner.test.mjs',
  'npm test -- -c tests/owner.test.mjs',
]) {
  assert.equal(hasImplementationProofCommand(command, nodeOptions), false, command);
  assert.equal(hasTestFirstProofCommand(command, nodeOptions), false, command);
}

for (const command of [
  'mocha --invert --grep . tests',
  'mocha --grep . --invert tests',
  'mocha --invert --fgrep . tests',
  'mocha -g. --invert tests',
]) {
  assert.equal(hasImplementationProofCommand(command, jsOptions), false, command);
  assert.equal(hasTestFirstProofCommand(command, jsOptions), false, command);
}

const jestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'jest' } };
const vitestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'vitest' } };
const compoundJestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'echo setup && jest' } };
const nestedJestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'npm run test:unit', 'test:unit': 'jest' } };
const internalNestedJestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'npm run test:unit -- --setupFilesAfterEnv=/tmp/exit0.js', 'test:unit': 'jest' } };
const safeInternalNestedJestPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: 'npm run test:unit -- --setupFilesAfterEnv test/setup.js', 'test:unit': 'jest' } };
const makeItFailPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { 'make-it-fail': 'jest tests/make-it-fail.test.js' } };
const nestedMakeItFailPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { 'make-it-fail': 'npm run test:fail', 'test:fail': 'jest tests/make-it-fail.test.js' } };
const internalNestedMakeItFailPackageOptions = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { 'make-it-fail': 'npm run test:fail -- --setupFilesAfterEnv=/tmp/exit0.js', 'test:fail': 'jest tests/make-it-fail.test.js' } };

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
  'npm test -- --setupFilesAfterEnv=/tmp/exit0.js',
  'npm run make-it-fail -- --setupFilesAfterEnv=/tmp/exit0.js',
]) {
  const options = command.includes('make-it-fail') ? makeItFailPackageOptions : nestedJestPackageOptions;
  assert.equal(hasImplementationProofCommand(command, options), false, command);
  assert.equal(hasTestFirstProofCommand(command, options), false, command);
}

assert.equal(hasTestFirstProofCommand('npm run make-it-fail -- --setupFilesAfterEnv=/tmp/exit0.js', nestedMakeItFailPackageOptions), false);
assert.equal(hasImplementationProofCommand('npm test', internalNestedJestPackageOptions), false);
assert.equal(hasTestFirstProofCommand('npm test', internalNestedJestPackageOptions), false);
assert.equal(hasTestFirstProofCommand('npm run make-it-fail', internalNestedMakeItFailPackageOptions), false);

for (const manager of ['pnpm', 'yarn']) {
  const options = { root: emptyRepo, proofStacks: ['js-package'], packageScripts: { test: `${manager} run test:unit -- --setupFilesAfterEnv=/tmp/exit0.js`, 'test:unit': 'jest' } };
  assert.equal(hasImplementationProofCommand('npm test', options), false, manager);
  assert.equal(hasTestFirstProofCommand('npm test', options), false, manager);
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
  'node --test --test-reporter spec tests/owner.test.mjs',
  'node --test --test-reporter reporters/node-test.mjs tests/owner.test.mjs',
  'node --test --test-global-setup test/setup.mjs tests/owner.test.mjs',
  'npm test -- --test-reporter spec',
  'npm test -- --test-reporter reporters/node-test.mjs',
  'npm test -- --test-global-setup test/setup.mjs',
]) {
  assert.equal(hasImplementationProofCommand(command, nodeOptions), true, command);
  assert.equal(hasTestFirstProofCommand(command, nodeOptions), true, command);
}

assert.equal(hasImplementationProofCommand('mocha --invert --grep owner tests', jsOptions), true);
assert.equal(hasTestFirstProofCommand('mocha --invert --grep owner tests', jsOptions), true);

for (const command of [
  'npm test -- --setupFilesAfterEnv test/setup.js tests/owner.test.js',
  'npm test -- --globalSetup test/global.js',
  'npm test -- --testEnvironment jest-environment-jsdom',
  'npm test -- -c jest.config.js',
  'npm test -- --unknown=local-value',
]) {
  assert.equal(hasImplementationProofCommand(command, jestPackageOptions), true, command);
  assert.equal(hasTestFirstProofCommand(command, jestPackageOptions), true, command);
}

assert.equal(hasImplementationProofCommand('npm test -- --setupFiles test/setup.ts', vitestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test -- --setupFiles test/setup.ts', vitestPackageOptions), true);

assert.equal(hasImplementationProofCommand('npm test -- --globalSetup test/global.js', compoundJestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test -- --globalSetup test/global.js', compoundJestPackageOptions), true);

assert.equal(hasImplementationProofCommand('npm test -- --setupFilesAfterEnv test/setup.js tests/owner.test.js', nestedJestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test -- --setupFilesAfterEnv test/setup.js tests/owner.test.js', nestedJestPackageOptions), true);
assert.equal(hasImplementationProofCommand('npm test', safeInternalNestedJestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm test', safeInternalNestedJestPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm run make-it-fail -- --setupFilesAfterEnv test/setup.js', makeItFailPackageOptions), true);
assert.equal(hasTestFirstProofCommand('npm run make-it-fail -- --setupFilesAfterEnv test/setup.js', nestedMakeItFailPackageOptions), true);

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

const nestedNodeScriptOptions = { root: emptyRepo, packageScripts: { test: 'npm run unit', unit: 'node --test src/owner.test.mjs' } };
const internalNestedNodeScriptOptions = { root: emptyRepo, packageScripts: { test: 'npm run unit -- --eval=process.exit(0)', unit: 'node --test src/owner.test.mjs' } };
const safeInternalNestedNodeScriptOptions = { root: emptyRepo, packageScripts: { test: 'npm run unit -- --test-reporter spec', unit: 'node --test src/owner.test.mjs' } };
assert.equal(hasImplementationProofCommand('npm test', nestedNodeScriptOptions), true);
assert.equal(hasTestFirstProofCommand('npm test', nestedNodeScriptOptions), true);
assert.equal(hasImplementationProofCommand('npm test -- --eval=process.exit(0)', nestedNodeScriptOptions), false);
assert.equal(hasTestFirstProofCommand('npm test -- --eval=process.exit(0)', nestedNodeScriptOptions), false);
assert.equal(hasImplementationProofCommand('npm test', internalNestedNodeScriptOptions), false);
assert.equal(hasTestFirstProofCommand('npm test', internalNestedNodeScriptOptions), false);
assert.equal(hasImplementationProofCommand('npm test', safeInternalNestedNodeScriptOptions), true);
assert.equal(hasTestFirstProofCommand('npm test', safeInternalNestedNodeScriptOptions), true);

for (const unitScript of [
  'node --test --help',
  'node --test --eval=process.exit(0)',
]) {
  const options = { root: emptyRepo, packageScripts: { test: 'npm run unit', unit: unitScript } };
  assert.equal(hasImplementationProofCommand('npm test', options), false, unitScript);
  assert.equal(hasTestFirstProofCommand('npm test', options), false, unitScript);
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
