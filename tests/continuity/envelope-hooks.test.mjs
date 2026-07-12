import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { handleHook } from '../../runtime/hook.mjs';
import { verifyEnvelope } from '../../runtime/lib/envelope.mjs';
import { auditPreToolHookResponses } from '../../runtime/lib/hook-coexistence.mjs';
import { resolveStore } from '../../runtime/lib/store.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

function preToolInput(repo, overrides = {}) {
  return {
    session_id: 'session-secret-a',
    turn_id: 'turn-secret-a',
    tool_use_id: 'tool-secret-a',
    cwd: repo,
    hook_event_name: 'PreToolUse',
    tool_name: 'mcp__hard_eng__state',
    tool_input: { action: 'status', _he: { forged: true } },
    ...overrides,
  };
}

test('unbound SessionStart is silent and creates no store or key', () => {
  const repo = makeRepo();
  const before = resolveStore(repo, { create: false });
  assert.equal(before.exists, false);
  const output = handleHook('session-start', {
    session_id: 'unbound-session',
    cwd: repo,
    hook_event_name: 'SessionStart',
    source: 'startup',
  }, { now: NOW });
  assert.equal(output, null);
  assert.equal(fs.existsSync(before.root), false);
});

test('exact PreToolUse overwrites forged envelope and signs bounded identity', () => {
  const repo = makeRepo();
  const input = preToolInput(repo);
  const output = handleHook('pre-tool-use', input, { now: NOW });
  const rewritten = output.hookSpecificOutput.updatedInput;
  assert.equal(output.hookSpecificOutput.permissionDecision, 'allow');
  assert.equal(rewritten.action, 'status');
  assert.equal(rewritten._he.forged, undefined);

  const store = resolveStore(repo, { create: false });
  const key = fs.readFileSync(store.keyPath);
  const verified = verifyEnvelope(rewritten._he, {
    key,
    action: 'status',
    now: NOW + 1,
  });
  assert.equal(verified.repo_id, store.repoId);
  assert.equal(verified.task_hash.length, 64);
  assert.doesNotMatch(JSON.stringify(rewritten._he), /session-secret-a|turn-secret-a|tool-secret-a/);
});

test('envelope verification rejects expiry, wrong operation, and tampering', () => {
  const repo = makeRepo();
  const output = handleHook('pre-tool-use', preToolInput(repo), { now: NOW });
  const envelope = output.hookSpecificOutput.updatedInput._he;
  const key = fs.readFileSync(resolveStore(repo, { create: false }).keyPath);
  assert.throws(() => verifyEnvelope(envelope, { key, action: 'event', now: NOW + 1 }), /operation/i);
  assert.throws(() => verifyEnvelope(envelope, { key, action: 'status', now: NOW + 120_000 }), /expired/i);
  assert.throws(() => verifyEnvelope({ ...envelope, signature: '0'.repeat(64) }, { key, action: 'status', now: NOW + 1 }), /signature/i);
  assert.throws(() => verifyEnvelope(envelope, {
    key,
    action: 'status',
    args: { action: 'status', payload: { tampered: true }, _he: envelope },
    now: NOW + 1,
  }), /input digest/i);
});

test('hook manifest owns only exact continuity events and matcher', () => {
  const hookFile = path.resolve('hooks/hooks.json');
  const text = fs.readFileSync(hookFile, 'utf8');
  const config = JSON.parse(text);
  assert.deepEqual(Object.keys(config.hooks).sort(), ['PreCompact', 'PreToolUse', 'SessionStart']);
  assert.equal(config.hooks.PreToolUse.length, 1);
  assert.equal(config.hooks.PreToolUse[0].matcher, '^mcp__hard_eng__state$');
  assert.doesNotMatch(text, /UserPromptSubmit|PostToolUse|Stop|Bash|apply_patch/);
});

test('Context Mode may observe but can never block or rewrite the binding envelope', () => {
  const hardEng = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'allow',
      updatedInput: { action: 'status', _he: { payload: 'signed', signature: 'signed' } },
    },
  };
  const contextMode = { hookSpecificOutput: { hookEventName: 'PreToolUse', additionalContext: 'Use Context Mode for large output.' } };
  assert.equal(auditPreToolHookResponses([
    { owner: 'hard-eng', output: hardEng },
    { owner: 'context-mode', output: contextMode },
  ]).status, 'PASS');
  assert.throws(() => auditPreToolHookResponses([
    { owner: 'hard-eng', output: hardEng },
    { owner: 'context-mode', output: { hookSpecificOutput: { permissionDecision: 'deny' } } },
  ]), /blocks/i);
  assert.throws(() => auditPreToolHookResponses([
    { owner: 'hard-eng', output: hardEng },
    { owner: 'context-mode', output: { hookSpecificOutput: { updatedInput: { action: 'status' } } } },
  ]), /sole updatedInput owner/i);
});
