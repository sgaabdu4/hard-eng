#!/usr/bin/env node
/**
 * Shared PreToolUse security hook.
 *
 * Reuses karanb192/claude-code-hooks checks, normalizes Claude/Codex/Copilot
 * hook payloads, and emits both Claude/Codex + Copilot denial shapes.
 */

const fs = require('fs');
const path = require('path');

const dangerous = require('./claude-code-hooks/block-dangerous-commands.js');
const protect = require('./claude-code-hooks/protect-secrets.js');

const SAFETY_LEVEL = process.env.AGENT_HOOK_SAFETY_LEVEL || process.env.CCH_SAFETY_LEVEL || 'high';
const LOG_DIR = process.env.AGENT_HOOK_LOG_DIR || path.join(process.env.HOME || process.cwd(), '.agents', 'hooks', 'logs');
const DANGER_EMOJIS = { critical: '🚨', high: '⛔', strict: '⚠️' };
const SECRET_EMOJIS = { critical: '🔐', high: '🛡️', strict: '⚠️' };

function summarizeText(value) {
  return { redacted: true, length: String(value || '').length };
}

function summarizePath(value) {
  return { redacted: true, length: String(value || '').length };
}

function sanitizeLogData(data) {
  const safe = {};
  for (const [key, value] of Object.entries(data)) {
    if (key === 'command' || key === 'cmd') safe[key] = summarizeText(value);
    else if (key === 'cwd' || key === 'filePath') safe[key] = summarizePath(value);
    else if (key === 'sessionId') safe[key] = value ? { redacted: true } : value;
    else safe[key] = value;
  }
  return safe;
}

function log(data) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const file = path.join(LOG_DIR, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    fs.appendFileSync(file, JSON.stringify({ ts: new Date().toISOString(), ...sanitizeLogData(data) }) + '\n');
  } catch {}
}

function parseMaybeJson(value) {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return value;
  try { return JSON.parse(trimmed); } catch { return value; }
}

function asObject(value) {
  const parsed = parseMaybeJson(value);
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
}

function normalizeToolName(name) {
  const raw = String(name || '').trim();
  const lower = raw.toLowerCase();
  if (lower === 'bash' || lower === 'shell' || lower === 'terminal') return 'Bash';
  if (lower === 'read') return 'Read';
  if (lower === 'edit' || lower === 'multiedit' || lower === 'multi_edit') return 'Edit';
  if (lower === 'write') return 'Write';
  if (lower === 'apply_patch' || lower === 'patch') return 'Patch';
  return raw;
}

function normalizePayload(payload) {
  const toolName = payload.tool_name ?? payload.toolName ?? payload.tool ?? payload.name;
  const rawInput = payload.tool_input ?? payload.toolArgs ?? payload.tool_args ?? payload.args ?? payload.input ?? {};
  const toolInput = asObject(rawInput);
  return {
    originalToolName: String(toolName || ''),
    toolName: normalizeToolName(toolName),
    toolInput,
    cwd: payload.cwd,
    sessionId: payload.session_id ?? payload.sessionId,
  };
}

function getCommand(toolName, input) {
  const command = input.command ?? input.cmd ?? input.script;
  if (typeof command === 'string') return command;
  if (toolName === 'Bash' && typeof input === 'string') return input;
  return '';
}

function addIfString(set, value) {
  if (typeof value === 'string' && value.trim()) set.add(value.trim());
}

function extractPatchPaths(command) {
  const paths = new Set();
  if (!command) return paths;

  const markers = /^\*\*\*\s+(?:Add|Update|Delete|Rename)\s+File:\s+(.+)$/gm;
  let match;
  while ((match = markers.exec(command))) addIfString(paths, match[1]);

  const diffMarkers = /^(?:---|\+\+\+)\s+(?:a|b)\/(.+)$/gm;
  while ((match = diffMarkers.exec(command))) addIfString(paths, match[1]);

  return paths;
}

function getFilePaths(toolName, input, command) {
  const paths = new Set();
  addIfString(paths, input.file_path);
  addIfString(paths, input.filePath);
  addIfString(paths, input.path);

  if (Array.isArray(input.paths)) {
    for (const value of input.paths) addIfString(paths, value);
  }

  if (toolName === 'Patch') {
    for (const value of extractPatchPaths(command)) addIfString(paths, value);
  }

  return [...paths];
}

function deny(reason, meta = {}) {
  log({ level: 'BLOCKED', reason, ...meta });
  const output = {
    permissionDecision: 'deny',
    permissionDecisionReason: reason,
    decision: 'block',
    reason,
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: reason,
    },
  };
  process.stdout.write(JSON.stringify(output));
}

function allow() {
  process.stdout.write('{}');
}

function checkDangerousCommand(command) {
  if (!command) return undefined;
  const result = dangerous.checkCommand(command, SAFETY_LEVEL);
  if (!result.blocked) return undefined;
  const pattern = result.pattern;
  const emoji = DANGER_EMOJIS[pattern.level] || '⛔';
  return { reason: `${emoji} [${pattern.id}] ${pattern.reason}`, pattern };
}

function checkSecretCommand(command, cwd) {
  if (!command) return undefined;
  const result = protect.checkBashCommand(command, SAFETY_LEVEL, { cwd });
  if (!result.blocked) return undefined;
  const pattern = result.pattern;
  const emoji = SECRET_EMOJIS[pattern.level] || '🛡️';
  return { reason: `${emoji} [${pattern.id}] Cannot execute: ${pattern.reason}`, pattern };
}

function checkSecretPath(filePath, action) {
  const result = protect.checkFilePath(filePath, SAFETY_LEVEL);
  if (!result.blocked) return undefined;
  const pattern = result.pattern;
  const emoji = SECRET_EMOJIS[pattern.level] || '🛡️';
  return { reason: `${emoji} [${pattern.id}] Cannot ${action}: ${pattern.reason}`, pattern };
}

function actionFor(toolName) {
  if (toolName === 'Read') return 'read';
  if (toolName === 'Write') return 'write to';
  if (toolName === 'Edit' || toolName === 'Patch') return 'modify';
  return 'access';
}

async function main() {
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  if (!input.trim()) return allow();

  try {
    const payload = JSON.parse(input);
    const event = normalizePayload(payload);
    const command = getCommand(event.toolName, event.toolInput);
    const filePaths = getFilePaths(event.toolName, event.toolInput, command);

    if (event.toolName === 'Bash') {
      const dangerousBlock = checkDangerousCommand(command);
      if (dangerousBlock) return deny(dangerousBlock.reason, {
        hook: 'block-dangerous-commands',
        id: dangerousBlock.pattern.id,
        priority: dangerousBlock.pattern.level,
        tool: event.originalToolName || event.toolName,
        command,
        sessionId: event.sessionId,
        cwd: event.cwd,
      });

      const secretBlock = checkSecretCommand(command, event.cwd);
      if (secretBlock) return deny(secretBlock.reason, {
        hook: 'protect-secrets',
        id: secretBlock.pattern.id,
        priority: secretBlock.pattern.level,
        tool: event.originalToolName || event.toolName,
        command,
        sessionId: event.sessionId,
        cwd: event.cwd,
      });
    }

    const action = actionFor(event.toolName);
    for (const filePath of filePaths) {
      const secretBlock = checkSecretPath(filePath, action);
      if (secretBlock) return deny(secretBlock.reason, {
        hook: 'protect-secrets',
        id: secretBlock.pattern.id,
        priority: secretBlock.pattern.level,
        tool: event.originalToolName || event.toolName,
        filePath,
        sessionId: event.sessionId,
        cwd: event.cwd,
      });
    }

    allow();
  } catch (error) {
    log({ level: 'ERROR', error: error && error.message ? error.message : String(error) });
    allow();
  }
}

main();
