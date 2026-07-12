import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');

function sourceFiles() {
  return execFileSync('git', [
    '-C', root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z',
  ]).toString('utf8').split('\0').filter(Boolean).sort();
}

test('the definitive source tree has one owner for every global surface', () => {
  const files = sourceFiles();
  const topLevel = [...new Set(files.map((file) => file.split('/')[0]))].sort();
  assert.deepEqual(topLevel, [
    '.github', '.gitignore', '.worktreeinclude', 'AGENTS.md', 'LICENSE',
    'README.md', 'THIRD_PARTY_NOTICES.md', 'assets', 'package.json', 'plugins',
    'scripts', 'tests',
  ]);

  for (const removed of [
    '.gitmodules', '.no-mistakes.yaml', 'agents/', 'codex/', 'hooks/',
    'integrations/', 'skills/', 'vendor/', 'tests/v2/',
  ]) {
    assert.equal(files.some((file) => file === removed || file.startsWith(removed)), false, `removed surface returned: ${removed}`);
  }

  const testOwners = [...new Set(files
    .filter((file) => file.startsWith('tests/'))
    .map((file) => file.split('/')[1]))].sort();
  assert.deepEqual(testOwners, [
    'build', 'continuity', 'contract', 'fixtures', 'learn', 'plan', 'plugin',
    'routing', 'setup', 'ship', 'state', 'ui', 'worktree',
  ]);
});

test('source contains no gitlinks, symlinks, oversized runtime owners, or second plan owner', () => {
  const files = sourceFiles();
  const staged = execFileSync('git', ['-C', root, 'ls-files', '--stage']).toString('utf8');
  assert.doesNotMatch(staged, /^160000 /m);
  assert.equal(files.includes('plan.md'), false);
  assert.match(fs.readFileSync(path.join(root, '.gitignore'), 'utf8'), /^plan\.md$/m);

  for (const relative of files) {
    const absolute = path.join(root, relative);
    if (!fs.existsSync(absolute)) continue;
    assert.equal(fs.lstatSync(absolute).isSymbolicLink(), false, `source symlink: ${relative}`);
    if (/^plugins\/hard-eng\/(?:runtime|skills\/hard-eng\/references)\/.+\.(?:mjs|md)$/.test(relative)) {
      const lines = fs.readFileSync(absolute, 'utf8').split(/\r?\n/).length;
      assert.ok(lines <= 700, `${relative} exceeds 700 lines: ${lines}`);
    }
  }
});

test('active instructions do not route through retired or split workflows', () => {
  const files = sourceFiles().filter((file) => (
    file === 'AGENTS.md'
    || /^plugins\/.+\/skills\/.+\/(?:SKILL\.md|references\/.+\.md)$/.test(file)
  ));
  const text = files.map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
  assert.doesNotMatch(text, /he-(?:plan|implement|verify|ship|learn)|workflow-help|grill-me/i);
  assert.doesNotMatch(text, /no-mistakes|treehouse|impeccable/i);
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  const commands = [...readme.matchAll(/```sh\n([\s\S]*?)```/g)].map((match) => match[1]).join('\n');
  assert.doesNotMatch(commands, /\b(?:no-mistakes|treehouse|impeccable)\b/i);
});

test('canonical CI can prove a migration candidate before a direct-main publication', () => {
  const workflow = fs.readFileSync(path.join(root, '.github', 'workflows', 'hard-eng.yml'), 'utf8');
  assert.match(workflow, /^\s*workflow_dispatch:\s*$/m);
  assert.match(workflow, /['"]codex\/\*\*['"]/);
  assert.match(workflow, /^\s*- main\s*$/m);
  assert.match(workflow, /he\.mjs check --all/);
});
