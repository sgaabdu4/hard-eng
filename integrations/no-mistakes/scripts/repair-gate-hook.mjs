#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const badGateArg = '--gate "$(pwd)"';
const goodGateArg = '--gate "$GATE_DIR"';
const gateDirLine = 'GATE_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"';
const badLogLine = 'LOG="$(pwd)/notify-push.log"';
const goodLogLine = 'LOG="$GATE_DIR/notify-push.log"';

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd || process.cwd(),
    encoding: 'utf8',
  });
}

function hasGateDirDefinition(text) {
  return /(^|\n)GATE_DIR=/.test(text);
}

function insertGateDirDefinition(text) {
  if (hasGateDirDefinition(text)) return text;
  if (text.includes('notify_failed=0')) return text.replace('notify_failed=0', `${gateDirLine}\nnotify_failed=0`);
  const shebang = text.match(/^#![^\n]*\n/);
  if (shebang) return `${shebang[0]}${gateDirLine}\n${text.slice(shebang[0].length)}`;
  return `${gateDirLine}\n${text}`;
}

export function repairHookText(text) {
  let next = text;
  if (next.includes(badLogLine)) {
    next = next.replace(badLogLine, hasGateDirDefinition(next) ? goodLogLine : `${gateDirLine}\n${goodLogLine}`);
  }
  if ((next.includes(badGateArg) || next.includes(goodGateArg)) && !hasGateDirDefinition(next)) {
    next = insertGateDirDefinition(next);
  }
  next = next.replaceAll(badGateArg, goodGateArg);
  return { text: next, changed: next !== text };
}

export function resolveGatePath(repo) {
  const result = run('git', ['-C', repo, 'remote', 'get-url', 'no-mistakes']);
  if (result.status !== 0) return '';
  const remote = result.stdout.trim();
  if (!remote || /^[a-z][a-z0-9+.-]*:\/\//i.test(remote) || /^[^/]+@[^:]+:/i.test(remote)) return '';
  return path.resolve(repo, remote);
}

export function repairGateHook(gatePath) {
  const hookPath = path.join(gatePath, 'hooks', 'post-receive');
  if (!fs.existsSync(hookPath)) return { status: 'skipped', hookPath };
  const original = fs.readFileSync(hookPath, 'utf8');
  const repaired = repairHookText(original);
  if (!repaired.changed) return { status: 'clean', hookPath };
  fs.writeFileSync(hookPath, repaired.text);
  fs.chmodSync(hookPath, 0o755);
  return { status: 'repaired', hookPath };
}

function parseArgs(argv) {
  if (argv[0] === '--gate') return { gate: argv[1] || '' };
  return { repo: argv[0] || process.cwd() };
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const gatePath = options.gate ? path.resolve(options.gate) : resolveGatePath(path.resolve(options.repo));
  if (!gatePath) {
    console.log('no-mistakes-gate-hook: skipped');
    return;
  }
  const result = repairGateHook(gatePath);
  console.log(`no-mistakes-gate-hook: ${result.status}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
