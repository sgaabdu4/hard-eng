import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SKILL_PARITY,
  SKILL_PARITY_BASELINE,
} from '../../runtime/lib/skill-parity.mjs';

const root = path.resolve('.');
const git = (args, options = {}) => execFileSync('git', ['-C', root, ...args], {
  encoding: 'utf8',
  ...options,
});
const lines = (value) => value.trim() ? value.trim().split(/\r?\n/) : [];
const digest = (value) => crypto.createHash('sha256').update(value).digest('hex');
const sourcePath = (row) => row.baseline_type === 'symlink'
  ? `skills/${row.name}`
  : `skills/${row.name}/SKILL.md`;

function baselineBytes(file) {
  return execFileSync('git', ['-C', root, 'show', `${SKILL_PARITY_BASELINE}:${file}`]);
}

function baselineFiles(name) {
  return lines(git(['ls-tree', '-r', '--name-only', SKILL_PARITY_BASELINE, '--', `skills/${name}`]));
}

function currentTrackedFiles(name) {
  return lines(git(['ls-files', '--', `skills/${name}`]));
}

function changedFiles(name) {
  return lines(git([
    'diff', '--name-status', '--no-renames', SKILL_PARITY_BASELINE, '--', `skills/${name}`,
  ]));
}

test('every pre-migration native skill is classified exactly once with retained-resource proof', () => {
  const baselineNames = lines(git([
    'ls-tree', '--name-only', `${SKILL_PARITY_BASELINE}:skills`,
  ]));
  assert.deepEqual(SKILL_PARITY.map((row) => row.name), baselineNames);
  assert.equal(new Set(SKILL_PARITY.map((row) => row.name)).size, baselineNames.length);
  assert.equal(SKILL_PARITY.length, 47);

  for (const row of SKILL_PARITY) {
    const entrypoint = sourcePath(row);
    const original = baselineBytes(entrypoint);
    assert.equal(digest(original), row.baseline_sha256, `${row.name} baseline digest drifted`);
    assert.ok([
      'retained-exact', 'retained-strengthened', 'consolidated', 'retired-approved',
    ].includes(row.disposition));

    if (row.disposition === 'retained-exact') {
      assert.deepEqual(changedFiles(row.name), [], `${row.name} is no longer byte-retained`);
      assert.deepEqual(currentTrackedFiles(row.name), baselineFiles(row.name));
      if (row.baseline_type === 'symlink') {
        const current = path.join(root, 'skills', row.name);
        assert.equal(fs.lstatSync(current).isSymbolicLink(), true, `${row.name} is no longer a symlink`);
        assert.equal(fs.readlinkSync(current), original.toString('utf8'));
        continue;
      }
      for (const file of baselineFiles(row.name)) {
        assert.deepEqual(fs.readFileSync(path.join(root, file)), baselineBytes(file), `${file} drifted`);
      }
      continue;
    }

    if (row.disposition === 'retained-strengthened') {
      const expected = row.changes.map(({ status, file }) => status === 'D' && file === null
        ? `${status}\tskills/${row.name}`
        : `${status}\tskills/${row.name}/${file}`);
      assert.deepEqual(changedFiles(row.name), expected, `${row.name} changed outside its reviewed ledger`);
      if (row.baseline_type === 'tree') {
        for (const file of baselineFiles(row.name)) {
          assert.equal(fs.existsSync(path.join(root, file)), true, `${row.name} lost ${file}`);
        }
      } else {
        assert.equal(original.toString('utf8').includes(row.baseline_marker), true,
          `${row.name} baseline adapter target drifted`);
      }
      for (const item of row.changes) {
        if (item.status === 'D' && row.baseline_type === 'symlink' && item.file === null) continue;
        assert.ok(['A', 'M'].includes(item.status), `${row.name} contains an unapproved destructive change`);
        const file = path.join(root, 'skills', row.name, item.file);
        assert.equal(fs.existsSync(file), true, `${row.name} change owner is missing: ${item.file}`);
        assert.equal(fs.readFileSync(file, 'utf8').includes(item.marker), true,
          `${row.name} reviewed marker is missing from ${item.file}`);
      }
      continue;
    }

    assert.equal(fs.existsSync(path.join(root, 'skills', row.name)), false,
      `${row.name} still exposes a parallel skill owner`);
    assert.deepEqual(currentTrackedFiles(row.name), []);
    assert.equal(original.toString('utf8').includes(row.baseline_marker), true,
      `${row.name} baseline marker is missing`);
    assert.ok(row.owners.length > 0, `${row.name} has no destination owner`);
    for (const item of row.owners) {
      const file = path.join(root, item.file);
      assert.equal(fs.existsSync(file), true, `${row.name} destination is missing: ${item.file}`);
      assert.equal(fs.readFileSync(file, 'utf8').includes(item.marker), true,
        `${row.name} destination marker is missing: ${item.marker}`);
    }
  }
});

test('only approved Impeccable and Treehouse entrypoints retire while no-mistakes is consolidated', () => {
  assert.deepEqual(
    SKILL_PARITY.filter((row) => row.disposition === 'retired-approved').map((row) => row.name),
    ['impeccable', 'treehouse'],
  );
  assert.equal(SKILL_PARITY.filter((row) => row.disposition === 'consolidated').length, 11);
  assert.equal(SKILL_PARITY.filter((row) => row.disposition.startsWith('retained-')).length, 34);
  assert.equal(SKILL_PARITY.find((row) => row.name === 'no-mistakes').disposition, 'consolidated');
});
