#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

const command = process.argv[2] ?? 'context-mode';
const args = process.argv.slice(3);
const timeoutMs = Number.parseInt(process.env.CONTEXT_MODE_MCP_PROBE_TIMEOUT_MS ?? '5000', 10);
const attempts = Number.parseInt(process.env.CONTEXT_MODE_MCP_PROBE_ATTEMPTS ?? '2', 10);
const requiredTools = [
  'ctx_batch_execute',
  'ctx_execute',
  'ctx_execute_file',
  'ctx_index',
  'ctx_search',
  'ctx_fetch_and_index',
  'ctx_stats',
];

function parseFrames(buffer) {
  const frames = [];
  let offset = 0;

  while (offset < buffer.length) {
    const headerEnd = buffer.indexOf('\r\n\r\n', offset);
    if (headerEnd === -1) break;

    const header = buffer.subarray(offset, headerEnd).toString('utf8');
    const match = /content-length:\s*(\d+)/i.exec(header);
    if (!match) {
      offset = headerEnd + 4;
      continue;
    }

    const length = Number.parseInt(match[1], 10);
    const bodyStart = headerEnd + 4;
    const bodyEnd = bodyStart + length;
    if (buffer.length < bodyEnd) break;

    frames.push(JSON.parse(buffer.subarray(bodyStart, bodyEnd).toString('utf8')));
    offset = bodyEnd;
  }

  return frames;
}

function parseLineMessages(buffer) {
  const messages = [];
  for (const line of buffer.toString('utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('{')) continue;
    try {
      messages.push(JSON.parse(trimmed));
    } catch {
      // Ignore partial lines while the process is still writing.
    }
  }
  return messages;
}

function parseMessages(buffer) {
  const frames = parseFrames(buffer);
  return frames.length > 0 ? frames : parseLineMessages(buffer);
}

function fail(message, stderr = '', stdout = '') {
  console.error(message);
  if (stderr.trim()) console.error(stderr.trim());
  if (stdout.trim()) console.error(stdout.trim());
  process.exit(1);
}

const initialize = {
  jsonrpc: '2.0',
  id: 1,
  method: 'initialize',
  params: {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'hard-eng-context-mode-probe', version: '1.0.0' },
  },
};
const initialized = { jsonrpc: '2.0', method: 'notifications/initialized', params: {} };
const toolsList = { jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} };

async function runProbe() {
  const child = spawn(command, args, {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: {
      ...process.env,
      CONTEXT_MODE_PLATFORM: process.env.CONTEXT_MODE_PLATFORM ?? 'codex',
      CONTEXT_MODE_DIR: process.env.CONTEXT_MODE_DIR ?? `${process.env.HOME}/.codex/context-mode`,
    },
  });
  let stdout = Buffer.alloc(0);
  let stderr = '';
  let spawnError = null;

  child.stdout.on('data', (chunk) => {
    stdout = Buffer.concat([stdout, chunk]);
  });
  child.stderr.on('data', (chunk) => {
    stderr += chunk.toString('utf8');
  });
  child.on('error', (error) => {
    spawnError = error;
  });

  try {
    child.stdin.write(`${JSON.stringify(initialize)}\n${JSON.stringify(initialized)}\n${JSON.stringify(toolsList)}\n`);
    child.stdin.end();
  } catch (error) {
    spawnError = error;
  }

  const deadline = Date.now() + timeoutMs;
  let frames = [];
  while (Date.now() < deadline) {
    frames = parseMessages(stdout);
    if (frames.some((message) => message.id === 2)) break;
    if (child.exitCode !== null || spawnError) break;
    await delay(100);
  }

  if (child.exitCode === null && !child.killed) child.kill('SIGTERM');

  return {
    frames: parseMessages(stdout),
    stderr,
    stdout: stdout.toString('utf8'),
    spawnError,
  };
}

function probeError(result) {
  if (result.spawnError) return `Failed to start context-mode: ${result.spawnError.message}`;

  const initializeResponse = result.frames.find((message) => message.id === 1);
  if (!initializeResponse?.result) {
    return 'context-mode did not return a valid initialize result.';
  }

  const toolsResponse = result.frames.find((message) => message.id === 2);
  if (!toolsResponse?.result?.tools) {
    return 'context-mode did not return a valid tools/list result.';
  }

  const toolNames = new Set(toolsResponse.result.tools.map((tool) => tool.name));
  const missing = requiredTools.filter((tool) => !toolNames.has(tool));
  if (missing.length > 0) return `context-mode missing required tools: ${missing.join(', ')}`;

  return null;
}

let lastResult = null;
let lastError = null;
for (let attempt = 1; attempt <= attempts; attempt += 1) {
  lastResult = await runProbe();
  lastError = probeError(lastResult);
  if (!lastError) {
    console.log(`context-mode MCP probe ok: ${requiredTools.join(', ')}`);
    process.exit(0);
  }
  if (attempt < attempts) await delay(500 * attempt);
}

fail(lastError, lastResult?.stderr ?? '', lastResult?.stdout ?? '');
