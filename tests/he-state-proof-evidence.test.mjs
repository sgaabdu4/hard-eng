#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  hasGreenProof,
  hasRedProof,
  hasTestQualityEvidence,
  matchesTestFirstProofGuardrail,
} from '../scripts/he-state-proof.mjs';
import { proofOptions } from './helpers/he-proof-options.mjs';

for (const evidence of [
  'test-quality not used; 1 failed test',
  'without test-quality; 1 failed test',
  'skipped test-quality; 1 failed test',
  'no test-quality; 1 failed test',
  'test-quality evidence missing; 1 failed test',
  'test-quality skill was skipped; 1 failed test',
  'test-quality scenario was not used; 1 failed test',
  'test-quality review missing; 1 failed test',
  'test-quality review is missing; 1 failed test',
  'test-quality scenarios are missing; 1 failed test',
  'test-quality review is disabled; 1 failed test',
  'test-quality scenarios are unavailable; 1 failed test',
  'test-quality skill was not loaded; 1 failed test',
  'test-quality skill; 1 failed test',
  'not recorded test-quality evidence; 1 failed test',
  'no recorded test-quality evidence; 1 failed test',
  'without used test-quality review; 1 failed test',
  'no used test-quality review; 1 failed test',
  'never used test-quality review; 1 failed test',
  'failed to use test-quality evidence; 1 failed test',
  'without `test-quality`; test-quality scenarios recorded; 1 failed test',
]) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), false, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail, proofOptions), false, evidence);
}

for (const evidence of ['test-quality scenarios recorded; 1 failed test', 'test-quality review was used; 1 failed test', 'used test-quality review; 1 failed test', 'loaded `test-quality`; 1 failed test']) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), true, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail, proofOptions), true, evidence);
}

for (const [command, evidence] of [
  ['npm test -- owner', 'test-quality scenarios recorded; mutation proof killed: 1 expected mutant before implementation'],
  ['npm test -- owner', 'test-quality scenarios recorded; mutation proof failed as expected before implementation'],
  ['npm test -- owner', 'test-quality scenarios recorded; make-it-fail failed as expected before implementation'],
  ['stryker run owner-mutants', 'test-quality scenarios recorded; 1 failed test'],
  ['npm run make-it-fail', 'test-quality scenarios recorded; 1 failed test'],
]) {
  assert.equal(matchesTestFirstProofGuardrail({
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command,
    evidence: [evidence],
  }, proofOptions), false, `${command}: ${evidence}`);
}

for (const evidence of ['1 failed, 5 passed; expected green button', '2 failed, 10 passed; expected clean label', 'red-first failed as expected for green button', 'red-first failed as expected for clean label', 'expected 1 failed test, got 1 failed, 5 passed', 'expected 1 failed test; recorded red output: 1 failed test', 'test-quality scenarios recorded; actual red output recorded: 1 failed test', 'mutation proof killed: 1 expected mutant before implementation', 'mutation proof failed as expected before implementation']) {
  assert.equal(hasRedProof(evidence), true, evidence);
}

for (const evidence of [
  'all tests passed green',
  'clean test run',
  '0 failed, 5 passed; expected green button',
  'test-quality scenarios recorded; expected 1 failed test but it did not fail',
  'test-quality scenarios recorded; expected 1 failed test but it did not run',
  'test-quality scenarios recorded; mutation score 0%; 0 killed, 1 survived',
  'test-quality scenarios recorded; mutation run: none killed',
  'test-quality scenarios recorded; mutation run failed as expected; 0 killed, 1 survived',
  'test-quality scenarios recorded; expected 1 failed test, got 5 passed',
  'test-quality scenarios recorded; expected 2 failing tests, actual 7 tests passed',
  'test-quality scenarios recorded; expected failures: 1 but passed',
  'test-quality scenarios recorded; expected 1 failed test',
  'test-quality scenarios recorded; expected 1 failed test recorded',
  'test-quality scenarios recorded; recorded failure expectation: expected 1 failed test',
  'test-quality scenarios recorded: expected 1 failed test',
  'test-quality scenarios recorded; should report 1 failed test',
  'test-quality scenarios recorded; would show 1 failing test',
  'test-quality scenarios recorded; 1 failed test expected',
  'test-quality scenarios recorded; failed: 1 expected',
  '1 mutant killed expected',
]) {
  assert.equal(hasRedProof(evidence), false, evidence);
}

for (const evidence of ['expected tests passed', 'should be green', 'would be clean', 'tests passed expected', 'green run expected']) {
  assert.equal(hasGreenProof(evidence), false, evidence);
}

for (const evidence of ['actual tests passed', 'green test run recorded', '5 passed, 1 skipped']) {
  assert.equal(hasGreenProof(evidence), true, evidence);
}

for (const evidence of [
  'test-quality scenarios recorded; mutation score 0%; 0 killed, 1 survived',
  'test-quality scenarios recorded; mutation run: none killed',
  'test-quality scenarios recorded; mutation run failed as expected',
  'test-quality scenarios recorded; mutation run failed as expected; 1 mutant survived',
  'test-quality scenarios recorded; mutation run failed as expected; survived mutants: 1',
  'test-quality scenarios recorded; mutation run failed as expected; 1 mutant escaped',
  'test-quality scenarios recorded; mutation run failed as expected; 1 mutation undetected',
  'test-quality scenarios recorded; mutation run failed as expected; mutation undetected: 1',
  'test-quality scenarios recorded; mutation run failed as expected; mutants undetected: 1',
  'test-quality scenarios recorded; mutation run failed as expected; 0 killed, 1 survived',
  'test-quality scenarios recorded; mutation proof did not fail; mutation proof failed as expected',
  'test-quality scenarios recorded; expected 1 mutant killed',
  'test-quality scenarios recorded; would report killed: 1 mutant',
  'test-quality scenarios recorded; recorded expected 1 mutant killed',
  'test-quality scenarios recorded; would report killed: 1 mutant recorded',
  'test-quality scenarios recorded; planned output killed: 1 mutant',
  'test-quality scenarios recorded; 1 mutant killed expected',
  'test-quality scenarios recorded; mutation killed: 1 expected',
]) {
  assert.equal(matchesTestFirstProofGuardrail({
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'stryker run owner-mutants',
    evidence: [evidence],
  }, proofOptions), false, evidence);
}

for (const evidence of [
  'test-quality scenarios recorded; make-it-fail did not fail; make-it-fail failed as expected',
  'test-quality scenarios recorded; make-it-fail was not red',
  'test-quality scenarios recorded; make-it-fail was not nonzero',
  'test-quality scenarios recorded; make-it-fail did not exit nonzero',
  'test-quality scenarios recorded; make-it-fail did not exit with nonzero',
  'test-quality scenarios recorded; make-it-fail should be red',
  'test-quality scenarios recorded; expected make-it-fail nonzero',
  'test-quality scenarios recorded; make-it-fail expected nonzero exit',
  'test-quality scenarios recorded; make-it-fail was expected nonzero exit',
  'test-quality scenarios recorded; make-it-fail was expected to be red',
  'test-quality scenarios recorded; make-it-fail confirmed',
  'test-quality scenarios recorded; make-it-fail reproduced',
  'test-quality scenarios recorded; make-it-fail passed',
  'test-quality scenarios recorded; make-it-fail green',
  'test-quality scenarios recorded; make-it-fail red output expected',
  'test-quality scenarios recorded; make-it-fail nonzero exit expected',
]) {
  assert.equal(matchesTestFirstProofGuardrail({
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm run make-it-fail',
    evidence: [evidence],
  }, proofOptions), false, evidence);
}

for (const [command, evidence] of [
  ['stryker run owner-mutants', 'test-quality scenarios recorded; all tests passed; 1 mutant killed'],
  ['stryker run owner-mutants', 'test-quality scenarios recorded; 0 failed, 5 passed; mutation killed: 1'],
  ['stryker run owner-mutants', 'test-quality scenarios recorded; mutation proof killed: 1 expected mutant before implementation'],
  ['stryker run owner-mutants', 'test-quality scenarios recorded; observed killed: 1 mutant'],
  ['npm run make-it-fail', 'test-quality scenarios recorded; all tests passed; make-it-fail failed as expected'],
  ['npm run make-it-fail', 'test-quality scenarios recorded; 0 failed, 5 passed; make-it-fail failed as expected'],
  ['npm run make-it-fail', 'test-quality scenarios recorded; make-it-fail red output recorded'],
  ['npm run make-it-fail', 'test-quality scenarios recorded; make-it-fail nonzero output recorded'],
]) {
  assert.equal(matchesTestFirstProofGuardrail({
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command,
    evidence: [evidence],
  }, proofOptions), true, evidence);
}

console.log('he-state-proof-evidence-test: pass');
