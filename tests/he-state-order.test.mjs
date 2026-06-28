#!/usr/bin/env node
import assert from 'node:assert/strict';
import { validateImplementOrder } from '../scripts/he-state-order.mjs';

const proof = (id, sequence, evidence) => ({
  id,
  stage: 'he-implement',
  kind: 'test',
  owner: id,
  command: 'npm test -- owner',
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
      { id: 'test-first', sequence: 1 },
      { id: 'owner-change', sequence: 3 },
    ],
    guardrails,
  }, errors);
  return errors;
}

assert.deepEqual(errorsFor([
  proof('test-first-proof', 4, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('test-first-proof', 2, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 4, 'post-change tests passed'),
]), []);

assert.deepEqual(errorsFor([
  proof('test-first-proof', 2, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 2, 'post-change tests passed'),
  proof('implementation-proof', 4, 'post-change tests passed'),
]), []);

assert.match(errorsFor([
  proof('test-first-proof', 4, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 4, 'post-change tests passed'),
]).join('\n'), /test-first-proof before owner-change/);

assert.match(errorsFor([
  proof('test-first-proof', 2, 'test-quality scenarios recorded; red-first failed as expected'),
  proof('implementation-proof', 2, 'post-change tests passed'),
]).join('\n'), /implementation-proof after owner-change/);

console.log('he-state-order-test: pass');
