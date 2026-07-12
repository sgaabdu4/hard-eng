import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { handleHook } from '../../runtime/hook.mjs';
import { handleStateAction } from '../../runtime/server.mjs';
import { runCommand } from '../../runtime/he.mjs';
import { resolveStore } from '../../runtime/lib/store.mjs';

function authorize(repo, sessionId, args, toolUseId = 'tool-1', now = Date.now()) {
  return handleHook('pre-tool-use', {
    session_id: sessionId,
    turn_id: 'turn-1',
    tool_use_id: toolUseId,
    cwd: repo,
    hook_event_name: 'PreToolUse',
    tool_name: 'mcp__hard_eng__state',
    tool_input: args,
  }, { now }).hookSpecificOutput.updatedInput;
}

function parseMessages(output) {
  return output.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

test('real stdio MCP initializes and lists only state', () => {
  const server = path.resolve('runtime/server.mjs');
  const input = [
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'test', version: '1' } } },
    { jsonrpc: '2.0', method: 'notifications/initialized', params: {} },
    { jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} },
  ].map((message) => JSON.stringify(message)).join('\n');
  const result = spawnSync(process.execPath, [server], { input: `${input}\n`, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const messages = parseMessages(result.stdout);
  assert.equal(messages.find((message) => message.id === 1).result.serverInfo.name, 'hard-eng');
  assert.deepEqual(messages.find((message) => message.id === 2).result.tools.map((tool) => tool.name), ['state']);
});

test('real stdio MCP executes an authorized state call', () => {
  const repo = makeRepo();
  const server = path.resolve('runtime/server.mjs');
  const args = authorize(repo, 'stdio-session', {
    action: 'start', payload: { objective: 'Exercise stdio', intent: { kind: 'plan', digest: 'a'.repeat(64) } },
  }, 'stdio-start');
  const call = { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'state', arguments: args } };
  const result = spawnSync(process.execPath, [server], { input: `${JSON.stringify(call)}\n`, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  const response = parseMessages(result.stdout)[0];
  assert.equal(response.result.isError, false);
  assert.equal(response.result.structuredContent.status, 'bound');
  assert.doesNotMatch(result.stdout, /stdio-session|\/Users\//);
});

test('read-only he CLI reports runs, status, capsule, doctor, and dry-run prune', () => {
  const repo = makeRepo();
  assert.equal(runCommand(['doctor', '--repo', repo]).status, 'PASS');
  const started = handleStateAction(authorize(repo, 'cli-session', {
    action: 'start', payload: { objective: 'Exercise the human CLI', intent: { kind: 'plan', digest: 'd'.repeat(64) } },
  }), { now: Date.now() + 1 });
  assert.equal(runCommand(['doctor', '--repo', repo]).status, 'PASS');
  assert.equal(runCommand(['runs', '--repo', repo])[0].run_id, started.run_id);
  assert.match(runCommand(['status', '--repo', repo, '--run', started.run_id]).capsule, /Hard Eng resume/);
  assert.match(runCommand(['capsule', '--repo', repo, '--run', started.run_id]), new RegExp(started.run_id));
  assert.deepEqual(runCommand(['prune', '--repo', repo, '--dry-run']), []);
  assert.throws(() => runCommand(['prune', '--repo', repo]), /dry-run/i);
});

test('bound SessionStart restores exact capsule and safe PreCompact is silent', () => {
  const repo = makeRepo();
  const started = handleStateAction(authorize(repo, 'bound-session', {
    action: 'start', payload: { objective: 'Resume exact state', intent: { kind: 'plan', digest: 'e'.repeat(64) } },
  }), { now: Date.now() + 1 });
  const resumed = handleHook('session-start', {
    session_id: 'bound-session', cwd: repo, hook_event_name: 'SessionStart', source: 'compact',
  });
  assert.match(resumed.hookSpecificOutput.additionalContext, new RegExp(started.run_id));
  assert.equal(handleHook('pre-compact', {
    session_id: 'bound-session', cwd: repo, hook_event_name: 'PreCompact', trigger: 'manual',
  }), null);
});

test('separate repositories and a second writer never cross-bind or enumerate', () => {
  const left = makeRepo('hard-eng-left-');
  const right = makeRepo('hard-eng-right-');
  const leftRun = handleStateAction(authorize(left, 'same-session-label', {
    action: 'start', payload: { objective: 'Left', intent: { kind: 'plan', digest: '1'.repeat(64) } },
  }), { now: Date.now() + 1 });
  const rightStatus = handleStateAction(authorize(right, 'same-session-label', { action: 'status' }, 'right-status'), { now: Date.now() + 2 });
  assert.deepEqual(rightStatus, { status: 'unbound' });
  assert.notEqual(resolveStore(left, { create: false }).repoId, resolveStore(right, { create: false }).repoId);

  assert.throws(() => handleStateAction(authorize(left, 'second-writer', {
    action: 'start', payload: { objective: 'Second', intent: { kind: 'plan', digest: '2'.repeat(64) } },
  }, 'second-start'), { now: Date.now() + 3 }), /already has a non-complete/i);
  const status = handleStateAction(authorize(left, 'unrelated-reader', { action: 'status' }, 'reader-status'), { now: Date.now() + 4 });
  assert.deepEqual(status, { status: 'unbound' });
  assert.doesNotMatch(JSON.stringify(status), new RegExp(leftRun.run_id));
});

test('MCP tool call rejects a missing hook envelope without creating state', () => {
  const repo = makeRepo();
  const server = path.resolve('runtime/server.mjs');
  const call = { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'state', arguments: { action: 'status' } } };
  const result = spawnSync(process.execPath, [server], { input: `${JSON.stringify(call)}\n`, encoding: 'utf8', cwd: repo });
  assert.equal(result.status, 0);
  const response = parseMessages(result.stdout)[0];
  assert.equal(response.result.isError, true);
  assert.match(response.result.content[0].text, /envelope/i);
  assert.equal(resolveStore(repo, { create: false }).exists, false);
  assert.equal(fs.existsSync(path.join(repo, 'plan.md')), false);
});
