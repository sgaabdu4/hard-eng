#!/usr/bin/env node
import assert from 'node:assert/strict';
import { validateImplementOrder, validateShipOrder } from '../scripts/he-state-order.mjs';
import { proofOptions } from './helpers/he-proof-options.mjs';

const proof = (id, sequence, evidence) => ({
  id,
  stage: 'he-implement',
  kind: 'test',
  owner: id,
  command: 'npm test -- owner',
  proofStacks: ['js-package', 'node'],
  packageScripts: { test: 'node --test tests/owner.test.mjs' },
  status: 'passed',
  evidence: [evidence],
  sequence,
});

function errorsFor(guardrails) {
  const errors = [];
  validateImplementOrder({
    stage: 'he-implement',
    next: { ready: true },
    subStages: [
      { id: 'ssot-owner-reuse', sequence: 1 },
      { id: 'test-first', sequence: 2 },
      { id: 'owner-change', sequence: 4 },
    ],
    guardrails,
  }, errors, proofOptions);
  return errors;
}

const shipGuardrail = (id, sequence) => ({
  id,
  stage: 'he-ship',
  kind: 'script',
  owner: id,
  command: id === 'no-mistakes'
    ? 'no-mistakes axi run --intent "ship verified feature"'
    : 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7',
  status: 'passed',
  evidence: [`${id}: pass`],
  sequence,
});

function shipErrorsFor(guardrails) {
  const errors = [];
  validateShipOrder({
    stage: 'he-ship',
    next: { ready: true },
    guardrails,
  }, errors);
  return errors;
}

assert.deepEqual(errorsFor([
  proof('test-first-proof', 3, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]), []);

assert.deepEqual(errorsFor([
  proof('test-first-proof', 3, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 3, 'post-change tests passed'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]), []);

assert.match(errorsFor([
  proof('test-first-proof', 5, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]).join('\n'), /test-first-proof before owner-change/);

assert.match(errorsFor([
  proof('test-first-proof', 5, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('test-first-proof', 3, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]).join('\n'), /test-first-proof before owner-change/);

assert.match(errorsFor([
  proof('test-first-proof', 3, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 3, 'post-change tests passed'),
]).join('\n'), /implementation-proof after owner-change/);

assert.match(errorsFor([
  proof('test-first-proof', 1, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]).join('\n'), /test-first-proof after ssot-owner-reuse/);

assert.match(errorsFor([
  proof('test-first-proof', 1, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('test-first-proof', 3, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 5, 'post-change tests passed'),
]).join('\n'), /test-first-proof after ssot-owner-reuse/);

assert.deepEqual(shipErrorsFor([
  shipGuardrail('no-mistakes', 4),
  shipGuardrail('pr-evidence', 5),
  shipGuardrail('pr-review-threads', 6),
  shipGuardrail('ci-or-skip', 7),
]), []);

assert.match(shipErrorsFor([
  shipGuardrail('pr-evidence', 5),
  shipGuardrail('no-mistakes', 6),
  shipGuardrail('pr-review-threads', 7),
  shipGuardrail('ci-or-skip', 8),
]).join('\n'), /pr-evidence after latest no-mistakes/);

assert.match(shipErrorsFor([
  shipGuardrail('no-mistakes', 4),
  shipGuardrail('pr-review-threads', 5),
  shipGuardrail('pr-evidence', 6),
  shipGuardrail('ci-or-skip', 7),
]).join('\n'), /pr-review-threads after current pr-evidence/);

assert.match(shipErrorsFor([
  shipGuardrail('no-mistakes', 4),
  shipGuardrail('pr-evidence', 5),
  shipGuardrail('ci-or-skip', 6),
  shipGuardrail('pr-review-threads', 7),
]).join('\n'), /ci-or-skip after current pr-review-threads/);

console.log('he-state-order-test: pass');
