import test from 'node:test';
import assert from 'node:assert/strict';
import { validateCommitMessage } from '../../runtime/lib/commit-message.mjs';

test('commit-message policy accepts a focused message and returns only bounded evidence', () => {
  const evidence = validateCommitMessage('Bind exact cutover inventory\n\nProve rollback for every approved link.\n');
  assert.deepEqual(Object.keys(evidence).sort(), ['evidence_digest', 'message_digest', 'subject_digest']);
  assert.match(evidence.message_digest, /^[a-f0-9]{64}$/);
  assert.match(evidence.subject_digest, /^[a-f0-9]{64}$/);
  assert.match(evidence.evidence_digest, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(evidence).includes('Bind exact'), false);
});

test('commit-message policy rejects co-authors, em dashes, dash prefixes, decoration, and unrelated metadata', () => {
  const invalid = [
    'Ship candidate\n\nCo-authored-by: Bot <bot@example.com>',
    'Ship candidate — exact proof',
    '- Ship candidate',
    'Ship candidate\n\n-----',
    'Ship candidate\n\nGenerated-by: Codex',
    'Ship candidate\n\nToken usage: 1234',
  ];
  for (const message of invalid) assert.throws(() => validateCommitMessage(message), /commit message/i);
});

test('commit-message policy rejects empty, binary, and oversized input', () => {
  assert.throws(() => validateCommitMessage('  \n'), /commit message/i);
  assert.throws(() => validateCommitMessage('Subject\0hidden'), /commit message/i);
  assert.throws(() => validateCommitMessage(`Subject\n\n${'x'.repeat(16_384)}`), /commit message/i);
});
