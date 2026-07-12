#!/usr/bin/env node
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import { renderCapsule } from './lib/capsule.mjs';
import { createEnvelope, taskHash } from './lib/envelope.mjs';
import { redactErrorMessage } from './lib/redact.mjs';
import {
  ensureStore,
  readKey,
  readLock,
  readRun,
  readSession,
  resolveStore,
} from './lib/store.mjs';

const STATE_TOOL_NAME = 'mcp__hard_eng__state';

function requireBaseInput(input, eventName) {
  if (!input || input.hook_event_name !== eventName || !input.session_id || !input.cwd) {
    throw new Error(`${eventName} hook input is incomplete.`);
  }
}

function boundRun(input) {
  const store = resolveStore(input.cwd, { create: false });
  if (!store.exists || !fs.existsSync(store.keyPath)) return null;
  const key = readKey(store);
  const hash = taskHash(key, input.session_id);
  const session = readSession(store, hash);
  if (!session || session.revoked || !session.run_id) return null;
  const run = readRun(store, session.run_id);
  if (
    !run
    || run.phase === 'Complete'
    || run.repo_id !== store.repoId
    || run.checkout_id !== store.checkoutId
    || run.lease.task_hash !== hash
    || run.lease.checkout_id !== store.checkoutId
  ) return null;
  return { store, session, run };
}

function sessionStart(input) {
  requireBaseInput(input, 'SessionStart');
  if (!['startup', 'resume', 'clear', 'compact'].includes(input.source)) throw new Error('SessionStart source is invalid.');
  const bound = boundRun(input);
  if (!bound) return null;
  return {
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: renderCapsule(bound.run),
    },
  };
}

function preCompact(input) {
  requireBaseInput(input, 'PreCompact');
  if (!['manual', 'auto'].includes(input.trigger)) throw new Error('PreCompact trigger is invalid.');
  const bound = boundRun(input);
  if (!bound) return null;
  const reason = bound.run.interruption
    ? 'Hard Eng has an unreconciled external action; run the recorded reconciliation command before compaction.'
    : bound.session.pending
      ? 'Hard Eng has a pending state action; reconcile it before compaction.'
      : readLock(bound.store, bound.run.run_id)
        ? 'Hard Eng state is actively locked; retry compaction after the writer completes.'
        : null;
  return reason ? { continue: false, stopReason: reason } : null;
}

function preToolUse(input, now) {
  requireBaseInput(input, 'PreToolUse');
  if (input.tool_name !== STATE_TOOL_NAME) throw new Error('PreToolUse matcher reached an unexpected tool.');
  if (!input.turn_id || !input.tool_use_id || !input.tool_input) throw new Error('PreToolUse identity/input is incomplete.');
  const store = ensureStore(input.cwd);
  const key = readKey(store);
  const envelope = createEnvelope({ key, store, hookInput: input, toolInput: input.tool_input, now });
  const { _he: ignored, ...original } = input.tool_input;
  return {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'allow',
      updatedInput: { ...original, _he: envelope },
    },
  };
}

export function handleHook(kind, input, { now = Date.now() } = {}) {
  if (kind === 'session-start') return sessionStart(input);
  if (kind === 'pre-compact') return preCompact(input);
  if (kind === 'pre-tool-use') return preToolUse(input, now);
  throw new Error(`Unknown Hard Eng hook: ${kind}.`);
}

function runCli() {
  const kind = process.argv[2];
  const raw = fs.readFileSync(0, 'utf8');
  try {
    if (Buffer.byteLength(raw) > 128 * 1024) throw new Error('Hook input exceeds 128 KiB.');
    const input = JSON.parse(raw);
    const output = handleHook(kind, input);
    if (output) process.stdout.write(`${JSON.stringify(output)}\n`);
  } catch (error) {
    const message = redactErrorMessage(error);
    if (kind === 'pre-tool-use') {
      process.stdout.write(`${JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: message,
        },
      })}\n`);
      return;
    }
    if (kind === 'pre-compact') {
      process.stdout.write(`${JSON.stringify({ continue: false, stopReason: message })}\n`);
      return;
    }
    process.stdout.write(`${JSON.stringify({ systemMessage: message })}\n`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) runCli();
