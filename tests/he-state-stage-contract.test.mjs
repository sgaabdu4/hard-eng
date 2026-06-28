#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-contract-'));
const stages = {
  'he-implement': [2, '/he:verify', 'he-plan', ['owner-read', 'test-first', 'owner-change', 'guardrails', 'learning-capture', 'state-update']],
  'he-verify': [3, '/he:ship', 'he-implement', ['tests', 'guardrails', 'reviews', 'fix-loop', 'learning-capture', 'state-update']],
  'he-ship': [4, 'loop-complete', 'he-verify', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update']],
  'he-learn': [5, 'loop-complete', 'he-ship', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
};

function run(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

function receipt(stage, next) {
  const statePath = 'he-state.json';
  const command = next.match(/\/he:[a-z-]+|loop complete/i)?.[0] || next;
  return { stage, state: statePath, decision: 'PASS', ownerProof: ['proof'], artifacts: [], blocker: 'none', next, handoverPrompt: `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: ${command}. Stage: ${stage}. State: ${statePath}. Next: ${next}. Read ${statePath} first. Do not use the previous chat transcript.` };
}

const g = (id, stage, command, blocksPush = false) => ({
  id,
  stage,
  kind: 'script',
  owner: id,
  command,
  status: 'passed',
  evidence: [`${id}: pass`],
  blocksPush,
});
const tq = (text) => `test-quality scenarios recorded; ${text}`;

function guardrails(stage) {
  if (stage === 'he-implement') {
    return [
      { ...g('deterministic-owner-scan', stage, 'node scripts/find-deterministic-owner.mjs --json --root . owner'), sequence: 1 },
      { ...g('test-first-proof', stage, 'npm test -- owner'), kind: 'test', evidence: [tq('red-first failed as expected before owner-change')], sequence: 2 },
      { ...g('implementation-proof', stage, 'npm test -- owner'), kind: 'test', evidence: ['post-change tests passed'], sequence: 4 },
    ];
  }
  if (stage === 'he-verify') return [g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true)];
  if (stage === 'he-ship') return [
    { ...g('git-status', stage, 'git status --short', true), kind: 'manual' },
    g('worktree-ready', stage, 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', true),
    g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true),
    g('no-mistakes', stage, 'no-mistakes axi run --intent "ship verified feature"', true),
    g('pr-evidence', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7', true),
    g('pr-review-threads', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7 --check-review-threads No open GitHub review threads', true),
    g('ci-or-skip', stage, 'gh run view --json conclusion,status CI passed', true),
  ];
  return [];
}
const inventoryIds = ['regex-scanners', 'git-hooks', 'lint-analyze-typecheck', 'ssot-scanners', 'fallow', 'react-doctor', 'repeat-mistake-prevention'];
const quotedOrCommentedRunnerCommands = [
  'echo "&& npm test"',
  'echo "&& npm test "',
  'printf "; pytest"',
  'printf "; pytest "',
  "echo '# npm test'",
  'echo ok # && npm test',
  'echo ok;# && npm test',
];
const assignmentSubstitutionRunnerCommands = [
  'FOO=$(echo npm test )',
  'FOO=`echo npm test `',
  'FOO=$(printf "; pytest")',
  'env FOO=$(echo npm test )',
];
const unreachableConditionalRunnerCommands = [
  'false && npm test -- owner',
  'true || npm test -- owner',
  'exit 0; npm test -- owner',
  'return 0; npm test -- owner',
  'exec true; npm test -- owner',
  `if false
then
npm test -- owner
fi`,
];
function guardrailInventory(entries = {}) {
  return { requiredGuardrails: inventoryIds.map((id) => entries[id] || { id, status: 'not_applicable', reason: `${id} not touched`, evidence: ['guardrail inventory reviewed'] }) };
}

function state(stage) {
  const [stageIndex, target, fromStage, subStageIds] = stages[stage];
  return {
    schema: 'he-state/v1',
    feature: 'stage-contract',
    updatedAt: '2026-06-26T00:00:00.000Z',
    stage,
    stageIndex,
    status: 'ready',
    currentStep: 'handoff',
    next: { target, ready: true, reason: 'contract proof clean' },
    steps: [{ id: '1', title: 'Stage proof', status: 'done', receipt: receipt(stage, target) }],
    subStages: subStageIds.map((id, index) => ({ id, title: id, status: 'done', evidence: [id], sequence: index + 1 })),
    findings: stage === 'he-learn' ? [{ id: 'learn-1', stage: 'he-ship', summary: 'Durable guard added', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['guard'], artifacts: [], status: 'fixed' }] : [],
    guardrails: guardrails(stage),
    guardrailInventory: ['he-implement', 'he-verify', 'he-ship'].includes(stage) ? guardrailInventory() : undefined,
    entryGate: { fromStage, decision: 'PASS', statePath: 'prior-he-state.json', evidence: [`${fromStage} PASS`] },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}

let result = run(state('he-implement'));
assert.equal(result.status, 0, result.stderr);

const ownerChangeBeforeTestFirst = state('he-implement');
ownerChangeBeforeTestFirst.subStages = ownerChangeBeforeTestFirst.subStages.map((item) => (
  item.id === 'test-first' ? { ...item, sequence: 4 } : item
));
result = run(ownerChangeBeforeTestFirst);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /test-first before owner-change/);

const testProofAfterOwnerChange = state('he-implement');
testProofAfterOwnerChange.guardrails = testProofAfterOwnerChange.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof' ? { ...guardrail, sequence: 4 } : guardrail
));
result = run(testProofAfterOwnerChange);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /test-first-proof before owner-change/);

const duplicateTestFirstProofUsesValidProofOrder = state('he-implement');
duplicateTestFirstProofUsesValidProofOrder.guardrails = duplicateTestFirstProofUsesValidProofOrder.guardrails.flatMap((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? [
      { ...guardrail, command: 'owner change recorded', evidence: ['test command recorded without red output'], sequence: 2 },
      { ...guardrail, command: 'npm test -- owner', evidence: [tq('red-first failed as expected before owner-change')], sequence: 4 },
    ]
    : [guardrail]
));
result = run(duplicateTestFirstProofUsesValidProofOrder);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /test-first-proof before owner-change/);

const implementationProofBeforeOwnerChange = state('he-implement');
implementationProofBeforeOwnerChange.guardrails = implementationProofBeforeOwnerChange.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof' ? { ...guardrail, sequence: 2 } : guardrail
));
result = run(implementationProofBeforeOwnerChange);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-proof after owner-change/);

const startedWithoutEntry = state('he-implement');
startedWithoutEntry.status = 'in_progress';
startedWithoutEntry.next.ready = false;
delete startedWithoutEntry.entryGate;
result = run(startedWithoutEntry);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-implement requires entryGate from he-plan/);

const noImplementationGuard = state('he-implement');
noImplementationGuard.guardrails = [];
result = run(noImplementationGuard);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail deterministic-owner-scan/);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const missingTestFirstProof = state('he-implement');
missingTestFirstProof.guardrails = missingTestFirstProof.guardrails.filter((guardrail) => guardrail.id !== 'test-first-proof');
result = run(missingTestFirstProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const renamedTestFirstProof = state('he-implement');
renamedTestFirstProof.guardrails = renamedTestFirstProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, id: 'red-first-proof' }
    : guardrail
));
result = run(renamedTestFirstProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const postHocTestOnly = state('he-implement');
postHocTestOnly.guardrails = postHocTestOnly.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm test -- owner', evidence: [tq('tests passed after implementation')] }
    : guardrail
));
result = run(postHocTestOnly);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const tddWordingWithoutRedProof = state('he-implement');
tddWordingWithoutRedProof.guardrails = tddWordingWithoutRedProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm test -- owner', evidence: [tq('TDD scenarios listed; test-first plan ready')] }
    : guardrail
));
result = run(tddWordingWithoutRedProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const wrongStageTestFirstProof = state('he-implement');
wrongStageTestFirstProof.guardrails = wrongStageTestFirstProof.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, stage: 'he-verify', command: 'npm test -- owner # red-first failed as expected', evidence: [tq('red-first failed as expected')] }
    : guardrail
));
result = run(wrongStageTestFirstProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const nonRunnableTestFirstCommand = state('he-implement');
nonRunnableTestFirstCommand.guardrails = nonRunnableTestFirstCommand.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'owner change recorded', evidence: [tq('red-first failed as expected')] }
    : guardrail
));
result = run(nonRunnableTestFirstCommand);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const redProofInCommandOnly = state('he-implement');
redProofInCommandOnly.guardrails = redProofInCommandOnly.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm test -- owner # red-first failed as expected', evidence: [tq('test command recorded without red output')] }
    : guardrail
));
result = run(redProofInCommandOnly);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

const missingTestQualityEvidence = state('he-implement');
missingTestQualityEvidence.guardrails = missingTestQualityEvidence.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, command: 'npm test -- owner', evidence: ['red-first failed as expected before owner-change'] }
    : guardrail
));
result = run(missingTestQualityEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail test-first-proof/);

for (const evidence of ['0 failing', '0 failing tests', '0 test failed', '0 tests failed', '0 failed, 5 passed, 1 skipped', '0 failed, 5 passed, 1 todo', '5 passed, 1 pending', 'mutation not run', '0/1 mutants killed', 'killed 0 mutants', 'no mutants were killed', 'no mutations were detected', '0 mutations detected', '0 mutants were killed', 'mutants killed: 0', 'mutation score 0%; killed: 0, survived: 1', 'mutation score 0%; detected: 0, survived: 1', 'mutation not detected', 'mutant not killed', 'mutants killed: none']) {
  const nonRedProof = state('he-implement');
  nonRedProof.guardrails = nonRedProof.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command: 'npm test -- owner', evidence: [tq(evidence)] }
      : guardrail
  ));
  result = run(nonRedProof);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail test-first-proof/);
}

for (const command of ['npm mutation', 'npm mutants']) {
  const invalidNpmMutationCommand = state('he-implement');
  invalidNpmMutationCommand.guardrails = invalidNpmMutationCommand.guardrails.map((guardrail) => (
    guardrail.id === 'test-first-proof'
      ? { ...guardrail, command, evidence: [tq('mutation proof killed expected mutant before implementation')] }
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
    ? { ...guardrail, command: 'stryker run owner-mutants', evidence: [tq('mutation proof killed expected mutant before implementation')] }
    : guardrail
));
result = run(mutationFallbackProof);
assert.equal(result.status, 0, result.stderr);

for (const [command, evidence] of [
  ['npm run mutation', 'mutation proof killed expected mutant before implementation'],
  ['pnpm mutation', 'mutation proof killed expected mutant before implementation'],
  ['yarn mutation', 'mutation proof killed expected mutant before implementation'],
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
  ['npm --prefix web test', '1 failed, 5 passed, 0 skipped'],
  ['pnpm --filter web test', '1 failed, 5 passed, 0 skipped'],
  ['yarn workspace web test', '1 failed, 5 passed, 0 skipped'],
  ['python -m pytest', '1 failed, 5 passed, 0 skipped'],
  ['npx -y vitest run', '1 failed test, 5 passed'],
  ['npx --yes jest', '1 failed test, 5 passed'],
  ['npx -y stryker run', 'mutation proof killed expected mutant before implementation'],
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

const missingImplementationProof = state('he-implement');
missingImplementationProof.guardrails = missingImplementationProof.guardrails.filter((guardrail) => guardrail.id !== 'implementation-proof');
result = run(missingImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const malformedImplementationProof = state('he-implement');
malformedImplementationProof.guardrails = malformedImplementationProof.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, kind: 'manual', command: 'owner change recorded', evidence: ['implementation proof recorded'] }
    : guardrail
));
result = run(malformedImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const implementationRunnerOnlyInEvidence = state('he-implement');
implementationRunnerOnlyInEvidence.guardrails = implementationRunnerOnlyInEvidence.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, command: 'owner change recorded', evidence: ['npm test -- owner: tests passed'] }
    : guardrail
));
result = run(implementationRunnerOnlyInEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const negativeImplementationProof = state('he-implement');
negativeImplementationProof.guardrails = negativeImplementationProof.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, command: 'npm test -- owner', evidence: ['tests did not pass'] }
    : guardrail
));
result = run(negativeImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const failingCountImplementationProof = state('he-implement');
failingCountImplementationProof.guardrails = failingCountImplementationProof.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, command: 'npm test -- owner', evidence: ['10 failing tests'] }
    : guardrail
));
result = run(failingCountImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

for (const evidence of ['not all tests passed', 'passed: 10, failed: 1']) {
  const failedGreenProof = state('he-implement');
  failedGreenProof.guardrails = failedGreenProof.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command: 'npm test -- owner', evidence: [evidence] }
      : guardrail
  ));
  result = run(failedGreenProof);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail implementation-proof/);
}

const redOnlyImplementationProof = state('he-implement');
redOnlyImplementationProof.guardrails = redOnlyImplementationProof.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, command: 'npm test -- owner # red-first failed as expected', evidence: ['failing test recorded before implementation'] }
    : guardrail
));
result = run(redOnlyImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

for (const evidence of ['post-change test not run', '0 passing', '0 passed, 5 skipped', 'pass', 'no tests passed', 'tests passed: 0', 'tests passed, failed=1', '10 passed, 1 error', 'passed: 10, errors=1', 'tests passed, errored=1', 'tests passed, failed 1', 'all tests passed; errors 1', 'tests passed with errors present', '1 passing, 1 failing']) {
  const nonGreenProof = state('he-implement');
  nonGreenProof.guardrails = nonGreenProof.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command: 'npm test -- owner', evidence: [evidence] }
      : guardrail
  ));
  result = run(nonGreenProof);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail implementation-proof/);
}

for (const command of ['manual test', 'owner change test', 'npx stryker run', 'npx -y stryker run', 'npm test-not-real', 'pytest-fake']) {
  const nonRunnableCommand = state('he-implement');
  nonRunnableCommand.guardrails = nonRunnableCommand.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command, evidence: ['tests passed'] }
      : guardrail
  ));
  result = run(nonRunnableCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail implementation-proof/);
}

const nonRunnerArgument = state('he-implement');
nonRunnerArgument.guardrails = nonRunnerArgument.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, command: 'echo jest', evidence: ['tests passed'] }
    : guardrail
));
result = run(nonRunnerArgument);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

for (const command of [...quotedOrCommentedRunnerCommands, ...assignmentSubstitutionRunnerCommands, ...unreachableConditionalRunnerCommands]) {
  const quotedOrCommentedImplementationCommand = state('he-implement');
  quotedOrCommentedImplementationCommand.guardrails = quotedOrCommentedImplementationCommand.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command, evidence: ['tests passed'] }
      : guardrail
  ));
  result = run(quotedOrCommentedImplementationCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail implementation-proof/);
}

for (const command of [
  'pnpm test -- owner',
  'yarn test owner',
  'vitest run owner',
  'jest owner',
  'pytest tests',
  'env NODE_ENV=test npm test -- owner',
  'NODE_ENV=test npm test -- owner',
  'npm --prefix web test',
  'pnpm --filter web test',
  'yarn workspace web test',
  'python -m pytest',
  'npx -y vitest run',
  'npx --yes jest',
  'echo setup && npm test -- owner',
  'false || pytest tests',
  'printf setup; vitest run owner',
]) {
  const validImplementationCommand = state('he-implement');
  validImplementationCommand.guardrails = validImplementationCommand.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command, evidence: ['tests passed'] }
      : guardrail
  ));
  result = run(validImplementationCommand);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of ['1 passing', '5 passed, 1 skipped', '5 passed, 1 pending', '5 passed, 1 todo']) {
  const validImplementationProofSummary = state('he-implement');
  validImplementationProofSummary.guardrails = validImplementationProofSummary.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command: 'npm test -- owner', evidence: [evidence] }
      : guardrail
  ));
  result = run(validImplementationProofSummary);
  assert.equal(result.status, 0, result.stderr);
}

const mixedRedSummary = state('he-implement');
mixedRedSummary.guardrails = mixedRedSummary.guardrails.map((guardrail) => (
  guardrail.id === 'test-first-proof'
    ? { ...guardrail, evidence: [tq('1 failed test, 5 passed')] }
    : guardrail
));
result = run(mixedRedSummary);
assert.equal(result.status, 0, result.stderr);

const wrongStageImplementationProof = state('he-implement');
wrongStageImplementationProof.guardrails = wrongStageImplementationProof.guardrails.map((guardrail) => (
  guardrail.id === 'implementation-proof'
    ? { ...guardrail, stage: 'he-verify' }
    : guardrail
));
result = run(wrongStageImplementationProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail implementation-proof/);

const missingHandover = state('he-verify');
delete missingHandover.steps[0].receipt.handoverPrompt;
result = run(missingHandover);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /handoverPrompt/);

const nonStringReceiptNext = state('he-verify');
nonStringReceiptNext.steps[0].receipt.next = { target: '/he:ship' };
result = run(nonStringReceiptNext);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /receipt\.next must be a string/);
assert.doesNotMatch(result.stderr, /TypeError/);

const badDeterministicScan = state('he-implement');
badDeterministicScan.guardrails = badDeterministicScan.guardrails.map((guardrail) => (
  guardrail.id === 'deterministic-owner-scan'
    ? { ...guardrail, command: 'node scripts/find-deterministic-owner.mjs --root . owner' }
    : guardrail
));
result = run(badDeterministicScan);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail deterministic-owner-scan/);

const missingGuardrailInventory = state('he-implement');
delete missingGuardrailInventory.guardrailInventory;
result = run(missingGuardrailInventory);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ready handoff requires guardrailInventory/);

const missingReactDoctorGuardrail = state('he-implement');
missingReactDoctorGuardrail.guardrailInventory = guardrailInventory({
  'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
});
result = run(missingReactDoctorGuardrail);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /react-doctor requires guardrails\[\] entry react-doctor/);

for (const id of inventoryIds) {
  const mismatchedGuardrailClass = state('he-implement');
  mismatchedGuardrailClass.guardrails.push(g('quality-gate', 'he-implement', 'node scripts/check-project-quality-gates.mjs --require-push-gate .'));
  mismatchedGuardrailClass.guardrailInventory = guardrailInventory({
    [id]: { id, status: 'required', guardrailId: 'quality-gate', evidence: [`${id} changed`] },
  });
  result = run(mismatchedGuardrailClass);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, new RegExp(`${id} requires guardrails\\[\\] entry quality-gate to match ${id}`));
}

for (const id of ['react-doctor', 'fallow']) {
  const fakeSameNamedGuardrail = state('he-implement');
  fakeSameNamedGuardrail.guardrails.push({
    id,
    stage: 'he-implement',
    kind: 'script',
    owner: 'scripts/check-project-quality-gates.mjs',
    command: 'node scripts/check-project-quality-gates.mjs --require-push-gate .',
    status: 'passed',
    evidence: ['quality gate passed'],
    blocksPush: false,
  });
  fakeSameNamedGuardrail.guardrailInventory = guardrailInventory({
    [id]: { id, status: 'required', guardrailId: id, evidence: [`${id} changed`] },
  });
  result = run(fakeSameNamedGuardrail);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, new RegExp(`${id} requires guardrails\\[\\] entry ${id} to match ${id}`));
}

for (const id of ['react-doctor', 'fallow']) {
  const fakeEvidenceOnlyGuardrail = state('he-implement');
  fakeEvidenceOnlyGuardrail.guardrails.push({
    id: 'quality-gate',
    stage: 'he-implement',
    kind: 'script',
    owner: 'scripts/check-project-quality-gates.mjs',
    command: 'node scripts/check-project-quality-gates.mjs --require-push-gate .',
    status: 'passed',
    evidence: [`${id} was mentioned in review notes`],
    blocksPush: false,
  });
  fakeEvidenceOnlyGuardrail.guardrailInventory = guardrailInventory({
    [id]: { id, status: 'required', guardrailId: 'quality-gate', evidence: [`${id} changed`] },
  });
  result = run(fakeEvidenceOnlyGuardrail);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, new RegExp(`${id} requires guardrails\\[\\] entry quality-gate to match ${id}`));
}

const matchingReactDoctorGuardrail = state('he-implement');
matchingReactDoctorGuardrail.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
matchingReactDoctorGuardrail.guardrailInventory = guardrailInventory({
  'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
});
result = run(matchingReactDoctorGuardrail);
assert.equal(result.status, 0, result.stderr);

const matchingFallowGuardrail = state('he-implement');
matchingFallowGuardrail.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --base origin/main'));
matchingFallowGuardrail.guardrailInventory = guardrailInventory({
  fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['JS/TS changed'] },
});
result = run(matchingFallowGuardrail);
assert.equal(result.status, 0, result.stderr);

const pendingGuard = state('he-verify');
pendingGuard.guardrails.push({ ...g('docs-proof', 'he-verify', 'node docs-proof.mjs'), status: 'planned', evidence: [] });
result = run(pendingGuard);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrails are planned, active, failed, or blocked/);

const duplicateSubStage = state('he-verify');
duplicateSubStage.subStages.push({ id: 'tests', title: 'duplicate tests', status: 'pending', evidence: [] });
result = run(duplicateSubStage);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires exactly one subStage tests/);

const missingPrEvidence = state('he-ship');
missingPrEvidence.subStages = missingPrEvidence.subStages.filter((item) => item.id !== 'pr-evidence');
result = run(missingPrEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires exactly one subStage pr-evidence/);

const badFindingOwner = state('he-ship');
badFindingOwner.findings = [{ id: 'proof-1', stage: 'he-ship', summary: 'E2E failed', ownerStage: 'he-ship', repairType: 'proof', ownerProof: [], artifacts: [], status: 'open' }];
result = run(badFindingOwner);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ownerStage must be he-verify for proof/);

const completeNotReady = state('he-verify');
completeNotReady.status = 'complete';
completeNotReady.next.ready = false;
result = run(completeNotReady);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ready or complete requires next.ready true/);

const shipLoopCompleteWithLearning = state('he-ship');
shipLoopCompleteWithLearning.findings = [{ id: 'learn-1', stage: 'he-ship', summary: 'Repeated TDD miss needs durable guard', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['tests/he-state-stage-contract.test.mjs'], artifacts: [], status: 'open' }];
result = run(shipLoopCompleteWithLearning);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /loop-complete requires open learning findings to route to \/he:learn/);

const shipLearnWithoutFinding = state('he-ship');
shipLearnWithoutFinding.next.target = '/he:learn';
shipLearnWithoutFinding.steps[0].receipt = receipt('he-ship', '/he:learn');
result = run(shipLearnWithoutFinding);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /handoff to \/he:learn requires an open learning finding/);

const shipLearnWithProcessFinding = state('he-ship');
shipLearnWithProcessFinding.next.target = '/he:learn';
shipLearnWithProcessFinding.steps[0].receipt = receipt('he-ship', '/he:learn');
shipLearnWithProcessFinding.findings = [{ id: 'process-1', stage: 'he-ship', summary: 'Process gap needs durable guard', ownerStage: 'he-learn', repairType: 'process', ownerProof: ['tests/he-state-stage-contract.test.mjs'], artifacts: [], status: 'open' }];
result = run(shipLearnWithProcessFinding);
assert.equal(result.status, 0, result.stderr);

const learnLoopCompleteWithOpenProcessFinding = state('he-learn');
learnLoopCompleteWithOpenProcessFinding.findings.push({ id: 'process-1', stage: 'he-ship', summary: 'Process gap still needs durable guard', ownerStage: 'he-learn', repairType: 'process', ownerProof: ['tests/he-state-stage-contract.test.mjs'], artifacts: [], status: 'open' });
result = run(learnLoopCompleteWithOpenProcessFinding);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /open learning findings/);

const blockedWithoutEvidence = state('he-verify');
blockedWithoutEvidence.status = 'blocked';
blockedWithoutEvidence.next.ready = false;
result = run(blockedWithoutEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /blocked requires a blocking finding or blocker entry/);

console.log('he-state-stage-contract-test: pass');
