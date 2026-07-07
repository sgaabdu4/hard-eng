#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-hard-eng-artifacts.mjs');

function makeRepo(name) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
  assert.equal(spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' }).status, 0);
  assert.equal(spawnSync('git', ['config', 'user.email', 'hard-eng@example.invalid'], { cwd: root, encoding: 'utf8' }).status, 0);
  assert.equal(spawnSync('git', ['config', 'user.name', 'Hard Eng Test'], { cwd: root, encoding: 'utf8' }).status, 0);
  return root;
}

function run(root, args = []) {
  return spawnSync('node', [script, ...args, root], { encoding: 'utf8' });
}

let root = makeRepo('hard-eng-artifacts-pass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'report.md'), 'Aggregate result: 7 steps passed; user identifiers redacted.\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'artifact summary'], { cwd: root, encoding: 'utf8' }).status, 0);
let result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-email');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /untracked artifact file/);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-staged-bypass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', 'artifacts/e2e/run/events.jsonl'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted-again"}\n');
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-head-bypass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'unsafe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted-in-worktree"}\n');
result = run(root, ['--head']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-extensionless-bypass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events'), '{"email":"person@fixture.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'unsafe extensionless artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-staged-extensionless-bypass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events'), '{"event":"redacted"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe extensionless artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events'), '{"email":"person@fixture.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', 'artifacts/e2e/run/events'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events'), '{"event":"redacted-again"}\n');
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-head-tree-only-untracked');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'report.md'), 'Aggregate result: identifiers redacted.\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe head artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'local'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'local', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
result = run(root, ['--head']);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-staged-tree-only-untracked');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'report.md'), 'Aggregate result: identifiers redacted.\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe staged artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'local'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'local', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
result = run(root, ['--staged']);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-head-tree-only-ignored');
fs.writeFileSync(path.join(root, '.gitignore'), 'artifacts/e2e/*/\n');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'report.md'), 'Aggregate result: identifiers redacted.\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe ignored head artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'local'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'local', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
result = run(root, ['--head']);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-rev-bypass');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'unsafe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
const unsafeArtifactRev = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'redact artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root, ['--rev', unsafeArtifactRev]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-ignored-proof');
fs.writeFileSync(path.join(root, '.gitignore'), 'artifacts/e2e/*/\n');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'example-feature'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'example-feature', 'events.jsonl'), '{"email":"person@fixture.test","session":"abcdef1234567890abcdef"}\n');
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /untracked artifact file/);
assert.match(result.stderr, /raw email <redacted>/);
assert.match(result.stderr, /session\/token\/credential-like value/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

for (const [name, ignoredPath] of [
  ['outputs', 'outputs/events.jsonl'],
  ['outputs-cache', 'outputs/cache/events.jsonl'],
  ['outputs-dist', 'outputs/dist/events.jsonl'],
  ['outputs-dot-cache', 'outputs/.cache/events.jsonl'],
  ['tmp', 'tmp/events.jsonl'],
  ['tmp-cache', 'tmp/cache/events.log'],
  ['tmp-build', 'tmp/build/events.log'],
  ['hooks-logs', 'hooks/logs/events.log'],
]) {
  root = makeRepo(`hard-eng-artifacts-ignored-${name}`);
  fs.writeFileSync(path.join(root, '.gitignore'), '/outputs/\n/tmp/\nhooks/logs/\n');
  fs.mkdirSync(path.dirname(path.join(root, ignoredPath)), { recursive: true });
  fs.writeFileSync(path.join(root, ignoredPath), '{"email":"person@fixture.test","session":"abcdef1234567890abcdef"}\n');
  result = run(root);
  assert.notEqual(result.status, 0, `${ignoredPath} should be scanned`);
  assert.match(result.stderr, new RegExp(ignoredPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(result.stderr, /untracked artifact file/);
  assert.match(result.stderr, /raw email <redacted>/);
  assert.match(result.stderr, /session\/token\/credential-like value/);
  assert.doesNotMatch(result.stderr, /customer@realco\.test/);
}

for (const ignoredPath of [
  'debug.log',
  'events.jsonl',
]) {
  root = makeRepo(`hard-eng-artifacts-ignored-extension-${ignoredPath.replaceAll('.', '-')}`);
  fs.writeFileSync(path.join(root, '.gitignore'), '*.log\n*.jsonl\n');
  fs.writeFileSync(path.join(root, ignoredPath), '{"email":"person@fixture.test","session":"abcdef1234567890abcdef"}\n');
  result = run(root);
  assert.notEqual(result.status, 0, `${ignoredPath} should be scanned`);
  assert.match(result.stderr, new RegExp(ignoredPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(result.stderr, /untracked artifact file/);
  assert.match(result.stderr, /raw email <redacted>/);
  assert.match(result.stderr, /session\/token\/credential-like value/);
}

root = makeRepo('hard-eng-artifacts-ignore-dependency-cache');
fs.writeFileSync(path.join(root, '.gitignore'), 'node_modules/\nvendor/\ntests/\ncache/\n.cache/\n.next/\nbuild/\ndist/\nskills/*/.codebase/\n**/node_modules/\n**/vendor/\n**/cache/\n');
for (const ignoredPath of [
  'node_modules/pkg/logs/events.log',
  'vendor/pkg/outputs/events.jsonl',
  'tests/tmp/events.jsonl',
  '.cache/logs/events.log',
  '.next/cache/logs/events.log',
  'build/logs/events.log',
  'dist/logs/events.log',
  'skills/demo/.codebase/logs/events.log',
  'packages/demo/node_modules/pkg/logs/events.log',
  'integrations/vendor/logs/events.log',
  'apps/demo/cache/logs/events.log',
]) {
  fs.mkdirSync(path.dirname(path.join(root, ignoredPath)), { recursive: true });
  fs.writeFileSync(path.join(root, ignoredPath), '{"email":"person@fixture.test","session":"abcdef1234567890abcdef"}\n');
}
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-large');
fs.mkdirSync(path.join(root, 'docs', 'planning', 'feature'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'planning', 'feature', 'raw-payload.json'), `${'x'.repeat(520 * 1024)}\n`);
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'raw payload'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /large text payload artifact/);

root = makeRepo('hard-eng-artifacts-large-binary');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'video.webm'), Buffer.alloc(9 * 1024 * 1024));
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'large binary artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /large binary artifact/);

const oversizedBinary = Buffer.alloc(33 * 1024 * 1024);

root = makeRepo('hard-eng-artifacts-large-staged-binary');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'video.webm'), oversizedBinary);
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'video.webm'), Buffer.alloc(1));
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /large binary artifact/);

root = makeRepo('hard-eng-artifacts-large-rev-binary');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'video.webm'), oversizedBinary);
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'large binary artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
const largeArtifactRev = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'video.webm'), Buffer.alloc(1));
result = run(root, ['--rev', largeArtifactRev]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /large binary artifact/);

console.log('hard-eng-artifacts-test: pass');
