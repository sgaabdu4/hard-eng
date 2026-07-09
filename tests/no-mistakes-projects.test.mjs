#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const script = path.join(repo, 'scripts', 'check-no-mistakes-projects.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'no-mistakes-projects-'));

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', ...options });
  if (options.expectFailure) return result;
  assert.equal(result.status, 0, `${command} ${args.join(' ')}\n${result.stdout}\n${result.stderr}`);
  return result;
}

function write(file, text, mode) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  if (mode) fs.chmodSync(file, mode);
}

function initRepo(root) {
  fs.mkdirSync(root, { recursive: true });
  run('git', ['init', '-q', '-b', 'main'], { cwd: root });
  run('git', ['remote', 'add', 'origin', 'https://github.com/example/repo.git'], { cwd: root });
  run('git', ['remote', 'add', 'no-mistakes', path.join(root, '.gate.git')], { cwd: root });
  write(path.join(root, '.no-mistakes.yaml'), 'commands:\n  test: "echo test"\n  lint: "echo lint"\n  format: "echo format"\n');
}

const clean = path.join(tmp, 'clean');
initRepo(clean);
let result = run(process.execPath, [script, '--json', clean]);
let payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.equal(payload.repos[0].path, '.');
assert.equal(payload.repos[0].hasNoMistakesConfig, true);
assert.equal(payload.repos[0].hasNoMistakesRemote, true);

const missingRemote = path.join(tmp, 'missing-remote');
initRepo(missingRemote);
run('git', ['remote', 'remove', 'no-mistakes'], { cwd: missingRemote });
result = run(process.execPath, [script, '--json', missingRemote], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /initialized with no-mistakes init/.test(blocker)));

const missingConfig = path.join(tmp, 'missing-config');
initRepo(missingConfig);
fs.rmSync(path.join(missingConfig, '.no-mistakes.yaml'));
result = run(process.execPath, [script, '--json', missingConfig], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /must define \.no-mistakes\.yaml/.test(blocker)));

const unmanaged = path.join(tmp, 'unmanaged');
initRepo(unmanaged);
write(path.join(unmanaged, 'nested', '.git', 'HEAD'), 'ref: refs/heads/main\n');
result = run(process.execPath, [script, '--json', unmanaged], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /unmanaged nested Git repo nested/.test(blocker)));

const configuredNested = path.join(tmp, 'configured-nested');
initRepo(configuredNested);
initRepo(path.join(configuredNested, 'nested'));
result = run(process.execPath, [script, '--json', configuredNested]);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.type === 'project'));
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.hasNoMistakesConfig));
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.hasNoMistakesRemote));

console.log('no-mistakes-projects: pass');
