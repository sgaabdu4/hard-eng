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
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'report.md'), 'Aggregate result: 7 steps passed; user identifiers redacted.\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'artifact summary'], { cwd: root, encoding: 'utf8' }).status, 0);
let result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-artifacts-email');
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"email":"customer@realco.test","event":"login"}\n');
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /untracked artifact file/);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-staged-bypass');
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'safe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"email":"customer@realco.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', 'docs/e2e/run/events.jsonl'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted-again"}\n');
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-head-bypass');
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"email":"customer@realco.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'unsafe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted-in-worktree"}\n');
result = run(root, ['--head']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-rev-bypass');
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"email":"customer@realco.test","event":"login"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'unsafe artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
const unsafeArtifactRev = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted"}\n');
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'redact artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root, ['--rev', unsafeArtifactRev]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-artifacts-ignored-proof');
fs.writeFileSync(path.join(root, '.gitignore'), 'docs/e2e/*/\n');
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'task-comments'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'task-comments', 'events.jsonl'), '{"email":"customer@realco.test","session":"abcdef1234567890abcdef"}\n');
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /untracked artifact file/);
assert.match(result.stderr, /raw email <redacted>/);
assert.match(result.stderr, /session\/token\/credential-like value/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

for (const [name, ignoredPath] of [
  ['outputs', 'outputs/events.jsonl'],
  ['tmp', 'tmp/events.jsonl'],
  ['hooks-logs', 'hooks/logs/events.log'],
]) {
  root = makeRepo(`hard-eng-artifacts-ignored-${name}`);
  fs.writeFileSync(path.join(root, '.gitignore'), '/outputs/\n/tmp/\nhooks/logs/\n');
  fs.mkdirSync(path.dirname(path.join(root, ignoredPath)), { recursive: true });
  fs.writeFileSync(path.join(root, ignoredPath), '{"email":"customer@realco.test","session":"abcdef1234567890abcdef"}\n');
  result = run(root);
  assert.notEqual(result.status, 0, `${ignoredPath} should be scanned`);
  assert.match(result.stderr, new RegExp(ignoredPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(result.stderr, /untracked artifact file/);
  assert.match(result.stderr, /raw email <redacted>/);
  assert.match(result.stderr, /session\/token\/credential-like value/);
  assert.doesNotMatch(result.stderr, /customer@realco\.test/);
}

root = makeRepo('hard-eng-artifacts-ignore-dependency-cache');
fs.writeFileSync(path.join(root, '.gitignore'), 'node_modules/\nvendor/\ntests/\n.cache/\n.next/\ndist/\n');
for (const ignoredPath of [
  'node_modules/pkg/logs/events.log',
  'vendor/pkg/outputs/events.jsonl',
  'tests/tmp/events.jsonl',
  '.cache/logs/events.log',
  '.next/cache/logs/events.log',
  'dist/logs/events.log',
]) {
  fs.mkdirSync(path.dirname(path.join(root, ignoredPath)), { recursive: true });
  fs.writeFileSync(path.join(root, ignoredPath), '{"email":"customer@realco.test","session":"abcdef1234567890abcdef"}\n');
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
fs.mkdirSync(path.join(root, 'docs', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs', 'e2e', 'run', 'video.webm'), Buffer.alloc(9 * 1024 * 1024));
assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
assert.equal(spawnSync('git', ['commit', '-m', 'large binary artifact'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /large binary artifact/);

console.log('hard-eng-artifacts-test: pass');
