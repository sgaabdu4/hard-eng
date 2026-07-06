#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  assignmentSubstitutionRunnerCommands,
  g,
  guardrailInventory,
  inventoryIds,
  quotedOrCommentedRunnerCommands,
  receipt,
  run,
  state,
  tq,
  unreachableConditionalRunnerCommands,
} from './helpers/he-state-stage-fixture.mjs';
import { targetCommandsFromText } from '../scripts/he-state-handover-targets.mjs';

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

for (const evidence of ['0 failing', '0 failing tests', '0 test failed', '0 tests failed', '0 failed, 5 passed, 1 skipped', '0 failed, 5 passed, 1 todo', '5 passed, 1 pending', 'mutation not run', '0/1 mutants killed', 'killed 0 mutants', 'no mutants were killed', 'no mutations were detected', '0 mutations detected', '0 mutants were killed', 'mutants killed: 0', 'mutation score 0%; killed: 0, survived: 1', 'mutation score 0%; detected: 0, survived: 1', 'mutation score 0%; 0 killed, 1 survived', 'mutation run: none killed', 'mutation not detected', 'mutant not killed', 'mutants killed: none']) {
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

{
  const expectedOnlyRedProof = state('he-implement');
  expectedOnlyRedProof.guardrails = expectedOnlyRedProof.guardrails.map((guardrail) => (guardrail.id === 'test-first-proof' ? { ...guardrail, evidence: [tq('expected 1 failed test, got 5 passed')] } : guardrail));
  result = run(expectedOnlyRedProof); assert.notEqual(result.status, 0); assert.match(result.stderr, /passed guardrail test-first-proof/);
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
  const scopedPackageImplementationCommand = state('he-implement');
  scopedPackageImplementationCommand.guardrails = scopedPackageImplementationCommand.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command, evidence: ['tests passed'] }
      : guardrail
  ));
  result = run(scopedPackageImplementationCommand);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /passed guardrail implementation-proof/);
}

for (const command of [
  'npm test --workspaces=true',
  'pnpm test --recursive=true',
  'NODE_OPTIONS=--require=/tmp/exit0.js jest',
  'go test -exec /tmp/true',
  'go test -overlay overlay.json',
  'node --test --import=file:///tmp/exit0.mjs',
  'node --test --import=file:/tmp/exit0.mjs',
]) {
  const unsafeProofCommand = state('he-implement');
  unsafeProofCommand.guardrails = unsafeProofCommand.guardrails.map((guardrail) => (
    guardrail.id === 'implementation-proof'
      ? { ...guardrail, command, evidence: ['tests passed'] }
      : guardrail
  ));
  result = run(unsafeProofCommand);
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

assert.deepEqual(targetCommandsFromText('Next: Do not use loop-complete yet'), []);
assert.deepEqual(targetCommandsFromText('Next: loop-complete'), ['loop-complete']);

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
