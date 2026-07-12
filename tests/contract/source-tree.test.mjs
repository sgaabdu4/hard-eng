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

test('the definitive source tree has one native owner for every global surface', () => {
  const files = sourceFiles();
  const topLevel = [...new Set(files.map((file) => file.split('/')[0]))].sort();
  assert.deepEqual(topLevel, [
    '.github', '.gitignore', '.gitmodules', '.worktreeinclude', 'AGENTS.md',
    'DESIGN.md', 'LICENSE', 'PRODUCT.md', 'README.md', 'THIRD_PARTY_NOTICES.md',
    'assets', 'hooks', 'package.json', 'runtime', 'scripts', 'skills', 'tests', 'vendor',
  ]);

  for (const absent of [
    'plugins/', 'integrations/', 'tests/v2/', 'agents/', 'codex/bin/',
  ]) {
    assert.equal(files.some((file) => file === absent.slice(0, -1) || file.startsWith(absent)), false, `parallel owner returned: ${absent}`);
  }
  assert.equal(files.some((file) => file.startsWith('tests/plugin/')), false);
});

test('source symlinks are limited to exact native skill views over pinned gitlinks', () => {
  const staged = execFileSync('git', ['-C', root, 'ls-files', '--stage'], { encoding: 'utf8' });
  const symlinks = staged.split(/\r?\n/).filter((line) => line.startsWith('120000 '))
    .map((line) => line.split('\t')[1]).sort();
  assert.deepEqual(symlinks, [
    'skills/appwrite-backend',
    'skills/building-flutter-apps',
    'skills/react-doctor',
    'skills/vercel-react-best-practices',
  ]);
  for (const relative of symlinks) {
    const target = fs.readlinkSync(path.join(root, relative));
    assert.match(target, /^\.\.\/vendor\/skill-upstreams\//);
    assert.equal(fs.existsSync(path.resolve(path.dirname(path.join(root, relative)), target, 'SKILL.md')), true);
  }
  assert.equal((staged.match(/^160000 /gm) ?? []).length, 7);

  const fallow = path.join(root, 'skills', 'fallow');
  assert.equal(fs.lstatSync(fallow).isDirectory(), true);
  const adapter = fs.readFileSync(path.join(fallow, 'SKILL.md'), 'utf8');
  assert.match(adapter, /pinned upstream owner/i);
  assert.match(adapter, /vendor\/skill-upstreams\/fallow-skills\/fallow\/skills\/fallow\/SKILL\.md/);
  assert.match(adapter, /TypeScript|JavaScript/);
  assert.match(adapter, /dry-run/i);
});

test('the native candidate contains no parallel lifecycle or plugin architecture', () => {
  const files = sourceFiles();
  for (const skill of ['workflow-help', 'grill-me', 'he-plan', 'he-implement', 'he-verify', 'he-ship', 'he-learn']) {
    assert.equal(files.some((file) => file.startsWith(`skills/${skill}/`)), false, `parallel lifecycle skill returned: ${skill}`);
  }
  assert.equal(files.some((file) => file.split('/').includes('.codex-plugin')), false);
});

test('runtime owners stay focused and one repository-root plan remains the feature SSOT', () => {
  const files = sourceFiles();
  assert.equal(files.includes('plan.md'), false);
  const gitignore = fs.readFileSync(path.join(root, '.gitignore'), 'utf8');
  assert.match(gitignore, /^\/plan\.md$/m);
  assert.match(gitignore, /^\.hard-eng-install\/$/m);
  for (const relative of files.filter((file) => /^runtime\/.+\.mjs$/.test(file))) {
    if (!fs.existsSync(path.join(root, relative))) continue;
    const lines = fs.readFileSync(path.join(root, relative), 'utf8').split(/\r?\n/).length;
    assert.ok(lines <= 700, `${relative} exceeds 700 lines: ${lines}`);
  }
});

test('owned text sources stay below 700 lines unless an explicit focused-owner exemption is reviewed', () => {
  const extensions = new Set(['.css', '.json', '.md', '.mjs', '.py', '.sh', '.svg', '.toml', '.yaml', '.yml']);
  const focusedLargeOwners = new Set([]);
  for (const relative of sourceFiles()) {
    if (relative.startsWith('vendor/') || !extensions.has(path.extname(relative))) continue;
    const absolute = path.join(root, relative);
    if (!fs.existsSync(absolute) || !fs.lstatSync(absolute).isFile()) continue;
    const lines = fs.readFileSync(absolute, 'utf8').split(/\r?\n/).length;
    assert.ok(
      lines <= 700 || focusedLargeOwners.has(relative),
      `${relative} exceeds 700 lines without a reviewed focused-owner exemption: ${lines}`,
    );
  }
});

test('canonical CI proves the same native registry used locally', () => {
  const workflow = fs.readFileSync(path.join(root, '.github', 'workflows', 'hard-eng.yml'), 'utf8');
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
  assert.match(workflow, /^\s*workflow_dispatch:\s*$/m);
  assert.match(workflow, /['"]codex\/\*\*['"]/);
  assert.match(workflow, /^\s*- main\s*$/m);
  assert.equal((workflow.match(/node runtime\/he\.mjs check --all/g) ?? []).length, 1);
  assert.match(pkg.scripts.test, /--test-concurrency=4/);
});
