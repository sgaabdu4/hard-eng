#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-vendor-skill-integrity.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'vendor-skill-integrity-'));
const vendor = path.join(tmp, 'vendor', 'skill-upstreams', 'demo');

function run(command, args, cwd = tmp) {
  return spawnSync(command, args, { cwd, encoding: 'utf8' });
}

function runWithEnv(command, args, cwd = tmp, env = {}) {
  return spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    env: { ...process.env, ...env },
  });
}

function git(args, cwd = tmp) {
  const result = run('git', args, cwd);
  assert.equal(result.status, 0, result.stderr);
  return result;
}

fs.mkdirSync(vendor, { recursive: true });
git(['init']);
git(['init'], vendor);
fs.writeFileSync(path.join(vendor, 'SKILL.md'), '# Demo\n');
git(['add', 'SKILL.md'], vendor);
git(['-c', 'user.name=Hard Eng', '-c', 'user.email=test@example.com', 'commit', '-m', 'init'], vendor);

let result = run('node', [script, tmp]);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /vendor-skill-integrity: pass/);
result = runWithEnv('node', [script, tmp], tmp, {
  GIT_DIR: path.join(tmp, '.git'),
  GIT_WORK_TREE: tmp,
});
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /vendor-skill-integrity: pass/);

fs.mkdirSync(path.join(tmp, 'vendor', 'skill-upstreams', 'uninitialized'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'README.md'), 'root change\n');
git(['add', 'README.md']);
result = run('node', [script, tmp]);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /vendor-skill-integrity: pass/);

fs.writeFileSync(path.join(vendor, 'SKILL.md'), '# Demo changed\n');
result = run('node', [script, tmp]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dirty vendored skill upstream/);

git(['checkout', '--', 'SKILL.md'], vendor);
fs.mkdirSync(path.join(tmp, 'vendor', 'skill-upstreams', 'tracked'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'vendor', 'skill-upstreams', 'tracked', 'SKILL.md'), '# Bad\n');
git(['add', 'vendor/skill-upstreams/tracked/SKILL.md']);
result = run('node', [script, tmp]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /repo-owned vendored skill file changed/);
git(['reset', '--hard']);

fs.mkdirSync(path.join(tmp, 'vendor', 'skill-upstreams', 'tracked-delete'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'vendor', 'skill-upstreams', 'tracked-delete', 'SKILL.md'), '# Bad delete\n');
git(['add', 'vendor/skill-upstreams/tracked-delete/SKILL.md']);
git(['-c', 'user.name=Hard Eng', '-c', 'user.email=test@example.com', 'commit', '-m', 'track vendored file']);
fs.unlinkSync(path.join(tmp, 'vendor', 'skill-upstreams', 'tracked-delete', 'SKILL.md'));
result = run('node', [script, tmp]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /repo-owned vendored skill file changed/);

git(['checkout', '--', 'vendor/skill-upstreams/tracked-delete/SKILL.md']);
const vendorHead = git(['rev-parse', 'HEAD'], vendor).stdout.trim();
git(['update-index', '--add', '--cacheinfo', `160000,${vendorHead},vendor/skill-upstreams/gitlink-demo`]);
git(['-c', 'user.name=Hard Eng', '-c', 'user.email=test@example.com', 'commit', '-m', 'track vendored gitlink']);
git(['rm', '--cached', 'vendor/skill-upstreams/gitlink-demo']);
result = run('node', [script, tmp]);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /vendor-skill-integrity: pass/);

git(['reset', '--hard']);
git(['update-index', '--add', '--cacheinfo', `160000,${vendorHead},vendor/skill-upstreams/gitlink-replaced`]);
git(['-c', 'user.name=Hard Eng', '-c', 'user.email=test@example.com', 'commit', '-m', 'track replaceable gitlink']);
git(['rm', '--cached', 'vendor/skill-upstreams/gitlink-replaced']);
fs.writeFileSync(path.join(tmp, 'vendor', 'skill-upstreams', 'gitlink-replaced'), '# Replaced\n');
git(['add', 'vendor/skill-upstreams/gitlink-replaced']);
result = run('node', [script, tmp]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /repo-owned vendored skill file changed/);

console.log('vendor-skill-integrity-test: pass');
