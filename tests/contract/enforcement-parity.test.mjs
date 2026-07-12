import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ENFORCEMENT_PARITY,
  ENFORCEMENT_PROOFS,
} from '../../runtime/lib/enforcement-parity.mjs';

const root = path.resolve('.');
const expectedLines = [
  4, 5, 6, 7, 8, 9, 10, 11, 12,
  15, 16, 17, 18, 19,
  22, 23, 24, 25, 26,
  29, 30, 31, 32,
  35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50,
  53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
];

test('every pre-migration AGENTS obligation has one active owner, disposition, context cost, and proof', () => {
  assert.deepEqual(ENFORCEMENT_PARITY.map((row) => row.source_line), expectedLines);
  assert.equal(new Set(ENFORCEMENT_PARITY.map((row) => row.id)).size, expectedLines.length);
  const baseline = execFileSync('git', ['-C', root, 'show', '59014f3:AGENTS.md'], { encoding: 'utf8' }).split(/\r?\n/);
  for (const row of ENFORCEMENT_PARITY) {
    assert.equal(row.source, `59014f3:AGENTS.md:${row.source_line}`);
    assert.match(baseline[row.source_line - 1], /^-/);
    assert.ok(['retained-strengthened', 'consolidated', 'retired-approved'].includes(row.disposition));
    assert.ok(['deterministic', 'semantic-plus-deterministic', 'semantic-release-dogfood'].includes(row.guard));
    assert.ok(['global-rule', 'on-demand-skill', 'runtime-only'].includes(row.context));
    assert.ok(Array.isArray(row.owners) && row.owners.length > 0);
    for (const owner of row.owners) {
      assert.equal(fs.existsSync(path.join(root, owner)), true, `${row.id} owner is missing: ${owner}`);
    }
    const proof = ENFORCEMENT_PROOFS[row.proof];
    assert.ok(proof, `${row.id} has no registered proof`);
    const proofText = fs.readFileSync(path.join(root, proof.file), 'utf8');
    assert.equal(proofText.includes(proof.marker), true, `${row.id} proof marker is missing: ${proof.marker}`);
  }
});

test('current global rules retain evidence, precedence, blast-radius, and report-shape obligations', () => {
  const text = fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
  assert.match(text, /Project or nested `AGENTS\.md` overrides global guidance/);
  assert.match(text, /underlying evidence/);
  assert.match(text, /hunk, function, or class level/);
  assert.match(text, /Verified`, `Inferred`, and `Unknown/);
  assert.match(text, /Semantic edits inspect direct callers, cross-package effects, schema\/index, cache\/storage keys/);
  assert.match(text, /Report `PASS`, `CONCERNS`, or `FAIL`, then Why, What, Risk, and Proof\/gaps/);
  assert.match(text, /Risk covers direct callers, cross-package behavior, schema\/index, cache\/storage keys/);
});
