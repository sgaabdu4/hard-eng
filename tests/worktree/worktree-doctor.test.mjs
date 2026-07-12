import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runCommand } from '../../plugins/hard-eng/runtime/he.mjs';
import { git, makeRepo } from '../fixtures/repo-fixture.mjs';

test('worktree doctor validates exact ignored inputs while Codex owns the copy', () => {
  const repo = makeRepo('hard-eng-worktree-doctor-');
  fs.writeFileSync(path.join(repo, '.gitignore'), 'local/\n.env.local\nnode_modules/\n');
  fs.mkdirSync(path.join(repo, 'local'));
  fs.writeFileSync(path.join(repo, 'local', 'fixture.json'), '{"safe":true}\n');
  fs.writeFileSync(path.join(repo, '.env.local'), 'PRIVATE_VALUE=never-read\n', { mode: 0o600 });
  git(repo, 'add', '.gitignore');
  git(repo, 'commit', '-qm', 'ignore local inputs');

  const before = fs.readdirSync(repo).sort();
  const safe = runCommand([
    'doctor', '--repo', repo, '--worktree', '--worktree-path', 'local/fixture.json',
  ]);
  assert.equal(safe.status, 'PASS');
  assert.deepEqual(safe.entries, [{
    path: 'local/fixture.json',
    status: 'PASS',
    classification: 'ignored-local-input',
    approval_required: false,
    source_type: 'file',
  }]);
  assert.deepEqual(fs.readdirSync(repo).sort(), before);
  assert.equal(fs.existsSync(path.join(repo, '.worktreeinclude')), false);
  assert.equal(safe.copy_owner, 'codex-managed-worktree');
  assert.equal(safe.mutation, 'performed-by-codex-at-worktree-creation');

  const secret = runCommand([
    'doctor', '--repo', repo, '--worktree', '--worktree-path', '.env.local',
  ]);
  assert.equal(secret.status, 'CONCERNS');
  assert.equal(secret.entries[0].approval_required, true);
  assert.match(secret.warning, /Codex-managed worktree/i);
  assert.doesNotMatch(JSON.stringify(secret), /PRIVATE_VALUE|never-read/);
});

test('worktree doctor rejects globs, tracked files, missing paths, unsafe roots, and symlinks', () => {
  const repo = makeRepo('hard-eng-worktree-reject-');
  fs.writeFileSync(path.join(repo, '.gitignore'), 'local/\n');
  fs.mkdirSync(path.join(repo, 'local'));
  fs.writeFileSync(path.join(repo, 'local', 'real.txt'), 'safe\n');
  fs.symlinkSync('real.txt', path.join(repo, 'local', 'link.txt'));
  git(repo, 'add', '.gitignore');
  git(repo, 'commit', '-qm', 'fixture ignore');
  for (const candidate of ['.*', '.env*', '**', '.git/config', '.codex/config.toml', 'node_modules', 'README.md', 'missing.txt', 'local/link.txt']) {
    const report = runCommand(['doctor', '--repo', repo, '--worktree', '--worktree-path', candidate]);
    assert.equal(report.status, 'FAIL', candidate);
  }
});

test('worktree doctor accepts safe hidden directories but requires nested secrets to be named exactly', () => {
  const repo = makeRepo('hard-eng-worktree-hidden-');
  fs.writeFileSync(path.join(repo, '.gitignore'), '.local-config/\nlocal/\n');
  fs.mkdirSync(path.join(repo, '.local-config'));
  fs.writeFileSync(path.join(repo, '.local-config', 'settings.json'), '{}\n');
  fs.mkdirSync(path.join(repo, 'local'));
  fs.writeFileSync(path.join(repo, 'local', '.env.test'), 'TOKEN=never-read\n', { mode: 0o600 });
  git(repo, 'add', '.gitignore');
  git(repo, 'commit', '-qm', 'ignore setup inputs');

  const safe = runCommand(['doctor', '--repo', repo, '--worktree', '--worktree-path', '.local-config']);
  assert.equal(safe.status, 'PASS');
  assert.equal(safe.entries[0].source_type, 'directory');

  const broadSecret = runCommand(['doctor', '--repo', repo, '--worktree', '--worktree-path', 'local']);
  assert.equal(broadSecret.status, 'FAIL');
  assert.equal(broadSecret.entries[0].classification, 'secret-descendant-must-be-explicit');
  assert.doesNotMatch(JSON.stringify(broadSecret), /TOKEN|never-read/);

  const exactSecret = runCommand(['doctor', '--repo', repo, '--worktree', '--worktree-path', 'local/.env.test']);
  assert.equal(exactSecret.status, 'CONCERNS');
  assert.equal(exactSecret.entries[0].approval_required, true);
});

test('checked-in .worktreeinclude is validated as the only proposed copy owner', () => {
  const repo = makeRepo('hard-eng-worktree-file-');
  fs.writeFileSync(path.join(repo, '.gitignore'), 'local/\n');
  fs.mkdirSync(path.join(repo, 'local'));
  fs.writeFileSync(path.join(repo, 'local', 'fixture.json'), '{}\n');
  fs.writeFileSync(path.join(repo, '.worktreeinclude'), 'local/fixture.json\n');
  git(repo, 'add', '.gitignore', '.worktreeinclude');
  git(repo, 'commit', '-qm', 'worktree include');
  const report = runCommand(['doctor', '--repo', repo, '--worktree']);
  assert.equal(report.status, 'PASS');
  assert.equal(report.entries[0].path, 'local/fixture.json');
});

test('worktree include owner must be tracked and parent symlinks cannot escape the repository', () => {
  const repo = makeRepo('hard-eng-worktree-owner-');
  fs.writeFileSync(path.join(repo, '.gitignore'), 'local/\n');
  fs.mkdirSync(path.join(repo, 'local'));
  fs.writeFileSync(path.join(repo, 'local', 'fixture.json'), '{}\n');
  fs.writeFileSync(path.join(repo, '.worktreeinclude'), 'local/fixture.json\n');
  git(repo, 'add', '.gitignore');
  git(repo, 'commit', '-qm', 'ignore local input');
  assert.throws(() => runCommand(['doctor', '--repo', repo, '--worktree']), /tracked/i);

  fs.unlinkSync(path.join(repo, '.worktreeinclude'));
  fs.rmSync(path.join(repo, 'local'), { recursive: true });
  const outside = fs.mkdtempSync(path.join(path.dirname(repo), 'hard-eng-outside-'));
  fs.writeFileSync(path.join(outside, 'fixture.json'), '{}\n');
  fs.symlinkSync(outside, path.join(repo, 'local'));
  const report = runCommand(['doctor', '--repo', repo, '--worktree', '--worktree-path', 'local/fixture.json']);
  assert.equal(report.status, 'FAIL');
  assert.match(report.entries[0].classification, /unsafe|invalid/);
});
