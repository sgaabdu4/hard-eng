#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  hasImplementationProofCommand,
  hasRedProof,
  hasTestFirstProofCommand,
  hasTestQualityEvidence,
  matchesTestFirstProofGuardrail,
} from '../scripts/he-state-proof.mjs';

for (const command of ['npm test || true', 'npm test; true', 'npm test | cat', 'npm test && true || true']) {
  assert.equal(hasImplementationProofCommand(command), false, command);
  assert.equal(hasTestFirstProofCommand(command), false, command);
}

for (const command of ['echo setup && npm test -- owner', 'printf setup; vitest run owner', 'false || pytest tests']) {
  assert.equal(hasImplementationProofCommand(command), true, command);
  assert.equal(hasTestFirstProofCommand(command), true, command);
}

for (const evidence of ['test-quality not used; 1 failed test', 'without test-quality; 1 failed test', 'skipped test-quality; 1 failed test', 'no test-quality; 1 failed test', 'test-quality evidence missing; 1 failed test']) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), false, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail), false, evidence);
}

for (const evidence of ['test-quality scenarios recorded; 1 failed test', 'used test-quality review; 1 failed test']) {
  const guardrail = {
    id: 'test-first-proof',
    stage: 'he-implement',
    kind: 'test',
    command: 'npm test -- owner',
    evidence: [evidence],
  };
  assert.equal(hasTestQualityEvidence(guardrail), true, evidence);
  assert.equal(matchesTestFirstProofGuardrail(guardrail), true, evidence);
}

for (const evidence of ['1 failed, 5 passed; expected green button', '2 failed, 10 passed; expected clean label']) {
  assert.equal(hasRedProof(evidence), true, evidence);
}

for (const evidence of ['all tests passed green', 'clean test run', '0 failed, 5 passed; expected green button']) {
  assert.equal(hasRedProof(evidence), false, evidence);
}

console.log('he-state-proof-test: pass');
