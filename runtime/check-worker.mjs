#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';

const [cwd, timeoutText, commandText] = process.argv.slice(2);
const command = JSON.parse(commandText);
const timeoutMs = Number.parseInt(timeoutText, 10);
const maxBytes = 2 * 1024 * 1024;
const hash = createHash('sha256');
let bytes = 0;
let timedOut = false;
let settled = false;

function observe(chunk) {
  if (bytes >= maxBytes) return;
  const value = chunk.subarray(0, Math.max(0, maxBytes - bytes));
  bytes += value.length;
  hash.update(value);
}

function killGroup(child, signal) {
  try {
    if (process.platform === 'win32') child.kill(signal);
    else process.kill(-child.pid, signal);
  } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
}

const child = spawn(command[0], command.slice(1), {
  cwd,
  env: process.env,
  detached: process.platform !== 'win32',
  stdio: ['ignore', 'pipe', 'pipe'],
  shell: false,
});
child.stdout.on('data', observe);
child.stderr.on('data', observe);
child.on('error', (error) => {
  if (settled) return;
  settled = true;
  clearTimeout(timer);
  process.stdout.write(`${JSON.stringify({
    status: null,
    signal: null,
    timed_out: false,
    error_code: error.code ?? 'SPAWN_ERROR',
    output_digest: hash.digest('hex'),
  })}\n`);
});

const timer = setTimeout(() => {
  timedOut = true;
  killGroup(child, 'SIGTERM');
  setTimeout(() => killGroup(child, 'SIGKILL'), 250).unref();
}, timeoutMs);

child.on('close', (code, signal) => {
  if (settled) return;
  settled = true;
  clearTimeout(timer);
  process.stdout.write(`${JSON.stringify({
    status: Number.isInteger(code) ? code : null,
    signal: signal ?? null,
    timed_out: timedOut,
    error_code: null,
    output_digest: hash.digest('hex'),
  })}\n`);
});
