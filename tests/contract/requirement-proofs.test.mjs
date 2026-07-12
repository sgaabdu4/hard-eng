import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { REQUIREMENT_PROOFS } from '../../runtime/lib/requirement-proofs.mjs';

const root = path.resolve('.');

test('R01 through R41 each bind current owners and executable proof markers exactly once', () => {
  assert.deepEqual(REQUIREMENT_PROOFS.map((row) => row.id), Array.from(
    { length: 41 }, (_, index) => `R${String(index + 1).padStart(2, '0')}`,
  ));
  for (const row of REQUIREMENT_PROOFS) {
    assert.ok(Array.isArray(row.owners) && row.owners.length > 0, `${row.id} has no owner`);
    for (const owner of row.owners) {
      assert.equal(fs.existsSync(path.join(root, owner)), true, `${row.id} owner is missing: ${owner}`);
    }
    assert.ok(Array.isArray(row.proofs) && row.proofs.length > 0, `${row.id} has no proof`);
    for (const proof of row.proofs) {
      const file = path.join(root, proof.file);
      assert.equal(fs.existsSync(file), true, `${row.id} proof file is missing: ${proof.file}`);
      assert.equal(fs.readFileSync(file, 'utf8').includes(proof.marker), true, `${row.id} proof marker is missing: ${proof.marker}`);
    }
    assert.ok(['none', 'explicit-model-quota-approval'].includes(row.release_gate));
  }
  assert.equal(REQUIREMENT_PROOFS.find((row) => row.id === 'R20').release_gate, 'explicit-model-quota-approval');
});
