#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { state as stageState } from './helpers/he-state-stage-fixture.mjs';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-live-currentness-'));
const gitRepo = path.join(tmp, 'repo');
fs.mkdirSync(gitRepo, { recursive: true });

function git(args) {
  return spawnSync('git', ['-C', gitRepo, ...args], { encoding: 'utf8' });
}

assert.equal(git(['init']).status, 0);
assert.equal(git(['config', 'user.email', 'hard-eng@example.invalid']).status, 0);
assert.equal(git(['config', 'user.name', 'Hard Eng Test']).status, 0);
fs.writeFileSync(path.join(gitRepo, 'README.md'), '# live currentness\n');
assert.equal(git(['add', 'README.md']).status, 0);
assert.equal(git(['commit', '-m', 'initial']).status, 0);
const head = git(['rev-parse', 'HEAD']).stdout.trim();

function shipState(recordedHead = head, currentHead = recordedHead) {
  const current = stageState('he-ship');
  current.guardrails = current.guardrails.map((guardrail) => {
    if (guardrail.id === 'pr-evidence') {
      return {
        ...guardrail,
        evidence: [`Current head: \`${currentHead}\`; No open no-mistakes findings; PR screenshots attached`],
      };
    }
    if (guardrail.id === 'ship-currentness') {
      return {
        ...guardrail,
        evidence: [`validated head: \`${recordedHead}\`; git status --short no output; worktree clean`],
      };
    }
    return guardrail;
  });
  return current;
}

function validate(current) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(current, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', '--live-currentness', '--repo', gitRepo, file], { encoding: 'utf8' });
}

let result = validate(shipState());
assert.equal(result.status, 0, result.stderr);

result = validate(shipState(head.slice(0, 12)));
assert.equal(result.status, 0, result.stderr);

result = validate(shipState(head.slice(0, 12), head));
assert.equal(result.status, 0, result.stderr);

result = validate(shipState('abcdef1234567890abcdef1234567890abcdef12'));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /head mismatch/);

fs.writeFileSync(path.join(gitRepo, 'dirty.txt'), 'dirty\n');
result = validate(shipState());
assert.notEqual(result.status, 0);
assert.match(result.stderr, /mixed dirty state classified as untracked/);

fs.unlinkSync(path.join(gitRepo, 'dirty.txt'));
fs.mkdirSync(path.join(gitRepo, 'vendor', 'skill-upstreams', 'demo'), { recursive: true });
fs.writeFileSync(path.join(gitRepo, 'vendor', 'skill-upstreams', 'demo', 'HEAD'), 'dirty\n');
result = validate(shipState());
assert.notEqual(result.status, 0);
assert.match(result.stderr, /vendor\/submodule/);

console.log('he-state-live-currentness-test: pass');
