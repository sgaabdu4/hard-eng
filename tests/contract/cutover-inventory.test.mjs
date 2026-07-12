import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { APPROVED_CUTOVER_INVENTORY } from '../../runtime/lib/approved-cutover-inventory.mjs';
import { validateCanonicalTeach } from '../../runtime/lib/live-cutover-owned.mjs';

const root = path.resolve('.');

test('approved destructive retirements are exact, parity-owned, and current-source only', () => {
  assert.equal(APPROVED_CUTOVER_INVENTORY.schema, 'hard-eng/approved-cutover-inventory/v1');
  const skillLinks = Object.entries(APPROVED_CUTOVER_INVENTORY.legacy_skill_links);
  assert.equal(skillLinks.length, 46);
  for (const [name, hash] of skillLinks) {
    assert.match(name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    assert.match(hash, /^[a-f0-9]{64}$/);
  }
  const backupLinks = Object.entries(APPROVED_CUTOVER_INVENTORY.legacy_backup_links);
  assert.equal(backupLinks.length, 9);
  for (const [relative, hash] of backupLinks) {
    assert.match(relative, /^\.codex\/(?:AGENTS\.md|hooks\.json)\.backup\.\d{8,}$/);
    assert.match(hash, /^[a-f0-9]{64}$/);
  }
  assert.equal(APPROVED_CUTOVER_INVENTORY.duplicate_teach.path, '.codex/skills/teach');
  assert.match(APPROVED_CUTOVER_INVENTORY.duplicate_teach.hash, /^[a-f0-9]{64}$/);
  assert.deepEqual(APPROVED_CUTOVER_INVENTORY.duplicate_teach.files, [
    'GLOSSARY-FORMAT.md', 'LEARNING-RECORD-FORMAT.md', 'MISSION-FORMAT.md',
    'RESOURCES-FORMAT.md', 'SKILL.md',
  ]);
  assert.equal(validateCanonicalTeach(root), true);

  const agents = Object.entries(APPROVED_CUTOVER_INVENTORY.custom_agents);
  assert.equal(agents.length, 25);
  const proofIds = new Set();
  for (const [name, entry] of agents) {
    assert.match(name, /^[A-Za-z0-9-]+\.toml$/);
    assert.match(entry.hash, /^[a-f0-9]{64}$/);
    assert.ok(Array.isArray(entry.owners) && entry.owners.length > 0, `${name} has no parity owner`);
    assert.equal(entry.proof_id, `custom-agent/${name.slice(0, -'.toml'.length)}`);
    assert.equal(proofIds.has(entry.proof_id), false, `${name} reuses a parity proof ID`);
    proofIds.add(entry.proof_id);
    let ownerText = '';
    for (const owner of entry.owners) {
      assert.equal(fs.existsSync(path.join(root, owner)), true, `${name} parity owner is missing: ${owner}`);
      ownerText = `${ownerText}\n${fs.readFileSync(path.join(root, owner), 'utf8')}`;
    }
    assert.ok(Array.isArray(entry.required_terms) && entry.required_terms.length > 0, `${name} has no parity obligation`);
    for (const term of entry.required_terms) {
      assert.equal(
        ownerText.toLowerCase().includes(term.toLowerCase()),
        true,
        `${name} parity obligation is absent from its owners: ${term}`,
      );
    }
  }
  assert.equal(proofIds.size, 25);
});
