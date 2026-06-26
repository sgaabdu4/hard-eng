#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';

const stableCommand = process.env.HOME ? `${process.env.HOME}/.codex/bin/codebase-memory-mcp` : '';
const command = process.argv[2] ?? (stableCommand && existsSync(stableCommand) ? stableCommand : 'codebase-memory-mcp');
const args = process.argv.slice(3);
const timeoutMs = Number.parseInt(process.env.CBM_MCP_PROBE_TIMEOUT_MS ?? '30000', 10);
const attempts = Number.parseInt(process.env.CBM_MCP_PROBE_ATTEMPTS ?? '3', 10);
const requiredTools = ['index_repository', 'search_graph', 'trace_path', 'search_code'];

function frame(message) {
  const body = JSON.stringify(message);
  return `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`;
}

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
    clientInfo: { name: 'hard-eng-probe', version: '1.0.0' },
  },
};
const initialized = { jsonrpc: '2.0', method: 'notifications/initialized', params: {} };
const toolsList = { jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} };

async function runProbe() {
  const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
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
    child.stdin.write(frame(initialize) + frame(initialized) + frame(toolsList));
    child.stdin.end();
  } catch (error) {
    spawnError = error;
  }

  const deadline = Date.now() + timeoutMs;
  let frames = [];
  while (Date.now() < deadline) {
    frames = parseFrames(stdout);
    if (frames.some((message) => message.id === 2)) break;
    if (child.exitCode !== null || spawnError) break;
    await delay(100);
  }

  if (child.exitCode === null && !child.killed) child.kill('SIGTERM');

  return {
    frames: parseFrames(stdout),
    stderr,
    stdout: stdout.toString('utf8'),
    spawnError,
  };
}

function probeError(result) {
  if (result.spawnError) return `Failed to start codebase-memory-mcp: ${result.spawnError.message}`;

  const initializeResponse = result.frames.find((message) => message.id === 1);
  if (!initializeResponse?.result) {
    return 'codebase-memory-mcp did not return a valid initialize result.';
  }

  const toolsResponse = result.frames.find((message) => message.id === 2);
  if (!toolsResponse?.result?.tools) {
    return 'codebase-memory-mcp did not return a valid tools/list result.';
  }

  const toolNames = new Set(toolsResponse.result.tools.map((tool) => tool.name));
  const missing = requiredTools.filter((tool) => !toolNames.has(tool));
  if (missing.length > 0) return `codebase-memory-mcp missing required tools: ${missing.join(', ')}`;

  return null;
}

let lastResult = null;
let lastError = null;
for (let attempt = 1; attempt <= attempts; attempt += 1) {
  lastResult = await runProbe();
  lastError = probeError(lastResult);
  if (!lastError) {
    console.log(`codebase-memory-mcp probe ok: ${requiredTools.join(', ')}`);
    process.exit(0);
  }
  if (attempt < attempts) await delay(500 * attempt);
}

fail(lastError, lastResult?.stderr ?? '', lastResult?.stdout ?? '');
