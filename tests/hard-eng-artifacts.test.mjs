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

root = makeRepo('hard-eng-artifacts-ignore');
fs.writeFileSync(path.join(root, '.gitignore'), 'tmp/\n');
fs.mkdirSync(path.join(root, 'tmp'), { recursive: true });
fs.writeFileSync(path.join(root, 'tmp', 'raw.log'), 'customer@realco.test\n');
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
