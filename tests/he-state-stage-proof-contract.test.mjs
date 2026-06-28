#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  assignmentSubstitutionRunnerCommands,
  quotedOrCommentedRunnerCommands,
  run,
  state,
  tq,
  unreachableConditionalRunnerCommands,
} from './helpers/he-state-stage-fixture.mjs';

let result;

const fakePackageScriptProof = state('he-implement');
fakePackageScriptProof.guardrails = fakePackageScriptProof.guardrails.map((guardrail) => (
  ['test-first-proof', 'implementation-proof'].includes(guardrail.id)
    ? {
      ...guardrail,
      command: 'npm run fake-pass',
      packageScripts: { 'fake-pass': 'node --test tests/owner.test.mjs' },
    }
    : guardrail
));
result = run(fakePackageScriptProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);
assert.match(result.stderr, /passed guardrail implementation-proof/);

for (const command of ['npm mutation', 'npm mutants']) {
  const invalidNpmMutationCommand = state('he-implement');
  invalidNpmMutationCommand.guardrails = invalidNpmMutationCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq('mutation proof killed: 1 expected mutant before implementation')] }
      : guardrail
  ));
  result = run(invalidNpmMutationCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail test-first-proof/);
}

const invalidNpmMakeItFailCommand = state('he-implement');
invalidNpmMakeItFailCommand.guardrails = invalidNpmMakeItFailCommand.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm make-it-fail', evidence: [tq('make-it-fail failed as expected before implementation')] }
    : guardrail
));
result = run(invalidNpmMakeItFailCommand);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

for (const command of ['npm test-not-real', 'pytest-fake']) {
  const fakeRunnerTestFirstCommand = state('he-implement');
  fakeRunnerTestFirstCommand.guardrails = fakeRunnerTestFirstCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq('red-first failed as expected before owner-change')] }
      : guardrail
  ));
  result = run(fakeRunnerTestFirstCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail test-first-proof/);
}

for (const command of [
  'npm --prefix web test',
  'npm --prefix . --workspace web test',
  'npm --workspace web test',
  'npm --workspaces test',
  'pnpm --dir packages/web test',
  'pnpm --dir . --filter web test',
  'pnpm --filter web test',
  'pnpm -r test',
  'pnpm --recursive test',
  'pnpm -w test',
  'yarn --cwd ./web test',
  'yarn --cwd . workspace web test',
  'yarn workspace web test',
]) {
  const scopedPackageTestFirstCommand = state('he-implement');
  scopedPackageTestFirstCommand.guardrails = scopedPackageTestFirstCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq('red-first failed as expected before owner-change')] }
      : guardrail
  ));
  result = run(scopedPackageTestFirstCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail test-first-proof/);
}

for (const command of [
  'npm_config_workspaces=true npm test',
  'npm_config_filter=web npm test',
  'npm_config_ws=true npm test',
  'pnpm_config_filter=web pnpm test',
  'pnpm_config_recursive=true pnpm test',
  'pnpm_config_workspace_root=true pnpm test',
  'env npm_config_workspaces=true npm test',
  'export pnpm_config_filter=web; pnpm test',
]) {
  for (const guardrailId of ['test-first-proof', 'implementation-proof']) {
    const scopedPackageEnvCommand = state('he-implement');
    scopedPackageEnvCommand.guardrails = scopedPackageEnvCommand.guardrails.map((guardrail) => (
      guardrail.id === guardrailId
        ? { ...guardrail, command, evidence: guardrailId === 'test-first-proof' ? [tq('red-first failed as expected before owner-change')] : guardrail.evidence }
        : guardrail
    ));
    result = run(scopedPackageEnvCommand);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, new RegExp(`passed guardrail ${guardrailId}`));
  }
}

for (const command of [...quotedOrCommentedRunnerCommands, ...assignmentSubstitutionRunnerCommands, ...unreachableConditionalRunnerCommands]) {
  const quotedOrCommentedTestFirstCommand = state('he-implement');
  quotedOrCommentedTestFirstCommand.guardrails = quotedOrCommentedTestFirstCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq('red-first failed as expected before owner-change')] }
      : guardrail
  ));
  result = run(quotedOrCommentedTestFirstCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail test-first-proof/);
}

const mutationFallbackProof = state('he-implement');
mutationFallbackProof.guardrails = mutationFallbackProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'stryker run owner-mutants', evidence: [tq('mutation proof killed: 1 expected mutant before implementation')] }
    : guardrail
));
result = run(mutationFallbackProof);
assert.equal(result.status, 0, result.stderr);

for (const [command, evidence] of [
  ['npm run mutation', 'mutation proof killed: 1 expected mutant before implementation'],
  ['pnpm mutation', 'mutation proof killed: 1 expected mutant before implementation'],
  ['yarn mutation', 'mutation proof killed: 1 expected mutant before implementation'],
  ['npm run make-it-fail', 'make-it-fail failed as expected before implementation'],
  ['pnpm make-it-fail', 'make-it-fail failed as expected before implementation'],
  ['yarn make-it-fail', 'make-it-fail failed as expected before implementation'],
  ['vitest run owner', '1 failed test, 5 passed'],
  ['jest owner', '1 failed test, 5 passed'],
  ['pytest tests', '1 failed test, 5 passed'],
  ['vitest run owner', '1 failed, 5 passed, 0 skipped'],
  ['pytest tests', '2 failed, 10 passed, 1 pending'],
  ['mocha tests', '1 failing'],
  ['ava tests', '1 test failed'],
  ['env NODE_ENV=test npm test -- owner', 'red-first failed as expected before owner-change'],
  ['NODE_ENV=test npm test -- owner', 'red-first failed as expected before owner-change'],
  ['python -m pytest', '1 failed, 5 passed, 0 skipped'],
  ['npx -y vitest run', '1 failed test, 5 passed'],
  ['npx --yes jest', '1 failed test, 5 passed'],
  ['npx -y stryker run', 'mutation proof killed: 1 expected mutant before implementation'],
  ['echo setup && npm test -- owner', 'red-first failed as expected before owner-change'],
  ['false || pytest tests', '1 failed test, 5 passed'],
  ['printf setup; vitest run owner', '1 failed test, 5 passed'],
]) {
  const validTestFirstCommand = state('he-implement');
  validTestFirstCommand.guardrails = validTestFirstCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq(evidence)] }
      : guardrail
  ));
  result = run(validTestFirstCommand);
  assert.equal(result.status, 0, result.stderr);
}

console.log('he-state-stage-proof-contract-test: pass');
