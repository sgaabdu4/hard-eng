#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const hook = path.join(process.env.HOME, '.agents', 'hooks', 'security-pretooluse.js');
const dangerousHook = path.join(process.env.HOME, '.agents', 'hooks', 'claude-code-hooks', 'block-dangerous-commands.js');
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'security-pretooluse-env-'));
const logDir = path.join(tempRoot, 'logs');

function runHook(payload) {
  const result = spawnSync('node', [hook], {
    input: JSON.stringify(payload),
    encoding: 'utf8',
    env: { ...process.env, AGENT_HOOK_LOG_DIR: logDir },
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout || '{}');
}

function assertDenied(payload, id) {
  const output = runHook(payload);
  assert.equal(output.permissionDecision, 'deny');
  assert.match(output.permissionDecisionReason, new RegExp(`\\[${id}\\]`));
}

function assertAllowed(payload) {
  const output = runHook(payload);
  assert.deepEqual(output, {});
}

assertDenied({
  tool_name: 'Read',
  tool_input: { file_path: '/tmp/.env.local' },
}, 'env-file');

assertDenied({
  tool_name: 'Bash',
  tool_input: { command: 'node --env-file=.env.local scripts/run.ts' },
  cwd: '/tmp',
}, 'env-file-loader');

const logFiles = fs.readdirSync(logDir).filter((name) => name.endsWith('.jsonl'));
assert.ok(logFiles.length > 0, 'security hook must write blocked events to the configured log dir');
const logText = logFiles.map((name) => fs.readFileSync(path.join(logDir, name), 'utf8')).join('\n');
assert.doesNotMatch(logText, /node --env-file=/, 'security hook log must not contain raw command text');
assert.doesNotMatch(logText, /"cwd":"\/tmp"/, 'security hook log must not contain raw cwd');
assert.match(logText, /"command":\{"redacted":true,"length":/);
assert.match(logText, /"cwd":\{"redacted":true,"length":/);

const dangerousHome = path.join(tempRoot, 'dangerous-home');
const dangerous = spawnSync('node', [dangerousHook], {
  input: JSON.stringify({
    tool_name: 'Bash',
    tool_input: { command: 'git reset --hard' },
    cwd: '/tmp/unsafe-project',
    session_id: 'session-123',
  }),
  encoding: 'utf8',
  env: { ...process.env, HOME: dangerousHome },
});
assert.equal(dangerous.status, 0, dangerous.stderr);
const dangerousLog = fs.readdirSync(path.join(dangerousHome, '.claude', 'hooks-logs'))
  .map((name) => fs.readFileSync(path.join(dangerousHome, '.claude', 'hooks-logs', name), 'utf8'))
  .join('\n');
assert.doesNotMatch(dangerousLog, /git reset --hard/);
assert.doesNotMatch(dangerousLog, /unsafe-project/);
assert.match(dangerousLog, /"cmd":\{"redacted":true,"length":/);

assertAllowed({
  tool_name: 'Bash',
  tool_input: { command: 'cat .env.example' },
  cwd: '/tmp',
});

fs.rmSync(tempRoot, { recursive: true, force: true });

console.log('security-pretooluse-env: pass');
