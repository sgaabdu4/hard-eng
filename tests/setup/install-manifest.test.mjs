import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import {
  INSTALL_MANIFEST_SCHEMA,
  validateInstallManifest,
} from '../../runtime/lib/install-manifest.mjs';
import {
  buildSetupPlan,
  readInstallManifestRecord,
} from '../../runtime/lib/setup-transaction.mjs';

function fixture() {
  return {
    schema: INSTALL_MANIFEST_SCHEMA,
    status: 'installed',
    version: '1.0.0',
    source_digest: 'a'.repeat(64),
    target_home_digest: 'b'.repeat(64),
    entries: [{
      path: '.agents/AGENTS.md',
      expected_type: 'file',
      source_hash: 'c'.repeat(64),
      installed_hash: 'c'.repeat(64),
      previous_target_hash: null,
      rollback_action: 'remove',
      mode: 0o644,
    }],
    rollback_bundle: null,
    updated_at: '2026-07-12T00:00:00.000Z',
    migration: [],
  };
}

test('install manifest accepts the exact current generation and empty one-time migration residue', () => {
  assert.equal(validateInstallManifest(fixture()), true);
});

test('install manifest rejects unknown fields, duplicate paths, hash drift, and executable-shape drift', () => {
  assert.throws(() => validateInstallManifest({ ...fixture(), unknown: true }), /unknown field/i);
  assert.throws(() => validateInstallManifest({
    ...fixture(), entries: [...fixture().entries, ...fixture().entries],
  }), /duplicated/i);
  assert.throws(() => validateInstallManifest({
    ...fixture(), entries: [{ ...fixture().entries[0], installed_hash: 'd'.repeat(64) }],
  }), /hashes differ/i);
  assert.throws(() => validateInstallManifest({
    ...fixture(), entries: [{ ...fixture().entries[0], expected_type: 'symlink' }],
  }), /symlink mode/i);
  assert.throws(() => validateInstallManifest({ ...fixture(), migration: ['legacy-mode'] }), /migration residue/i);
});

test('install manifest reader refuses a symlink and binds exact manifest bytes into setup approval', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-manifest-home-'));
  const installRoot = path.join(home, '.agents', '.hard-eng-install');
  fs.mkdirSync(installRoot, { recursive: true });
  const manifestFile = path.join(installRoot, 'manifest.json');
  const outside = path.join(home, 'outside-manifest.json');
  fs.writeFileSync(outside, `${JSON.stringify(fixture())}\n`);
  fs.symlinkSync(outside, manifestFile);
  assert.throws(() => readInstallManifestRecord(home), /unsafe|symlink/i);

  fs.unlinkSync(manifestFile);
  const value = {
    ...fixture(),
    target_home_digest: sha256(path.resolve(home)),
    entries: [],
  };
  fs.writeFileSync(manifestFile, `${JSON.stringify(value)}\n`, { mode: 0o600 });
  const sourceRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-manifest-source-'));
  fs.writeFileSync(path.join(sourceRoot, 'package.json'), '{"name":"fixture","version":"1.0.0"}\n');
  const codexMcp = {
    status: 'PASS', configured: true, evidence_digest: 'e'.repeat(64),
  };
  const first = buildSetupPlan({ mode: 'update', home, sourceRoot, codexMcp });
  value.updated_at = '2026-07-12T00:00:01.000Z';
  fs.writeFileSync(manifestFile, `${JSON.stringify(value)}\n`, { mode: 0o600 });
  const second = buildSetupPlan({ mode: 'update', home, sourceRoot, codexMcp });

  assert.notEqual(first.existing_manifest_hash, second.existing_manifest_hash);
  assert.notEqual(first.plan_digest, second.plan_digest);
});
