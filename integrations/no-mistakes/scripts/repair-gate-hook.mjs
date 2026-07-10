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
const dispatcherMarker = '# Managed by hard-eng no-mistakes gate dispatcher.';

function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd || process.cwd(),
    encoding: 'utf8',
    env: options.env || process.env,
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

export function resolveGatePath(repo, options = {}) {
  const result = run('git', ['-C', repo, 'remote', 'get-url', 'no-mistakes'], options);
  if (result.status !== 0) return '';
  const remote = result.stdout.trim();
  if (!remote || /^[a-z][a-z0-9+.-]*:\/\//i.test(remote) || /^[^/]+@[^:]+:/i.test(remote)) return '';
  return path.resolve(repo, remote);
}

function stripShellComments(text) {
  let output = '';
  let quote = '';
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (escaped) {
      output += char;
      escaped = false;
      continue;
    }
    if (char === '\\' && quote !== "'") {
      output += char;
      escaped = true;
      continue;
    }
    if (quote) {
      output += char;
      if (char === quote) quote = '';
      continue;
    }
    if (char === "'" || char === '"') {
      output += char;
      quote = char;
      continue;
    }
    if (char === '#' && (!output.length || /\s/.test(output.at(-1)))) {
      while (index < text.length && text[index] !== '\n') index += 1;
      if (index < text.length) output += '\n';
      continue;
    }
    output += char;
  }
  return output;
}

function shellWords(segment) {
  const words = [];
  let word = '';
  let quote = '';
  let escaped = false;
  const push = () => {
    if (word) words.push(word);
    word = '';
  };
  for (const char of segment) {
    if (escaped) {
      word += char;
      escaped = false;
      continue;
    }
    if (char === '\\' && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = '';
      else word += char;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) push();
    else word += char;
  }
  push();
  return words;
}

function hookStatements(text) {
  return stripShellComments(text)
    .replace(/\\\r?\n/g, ' ')
    .split(/[;\n]/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function notifyPushInvocation(statement) {
  if (/(^|[^|])\|([^|]|$)|(^|[^&])&([^&]|$)/.test(statement)) return null;
  const guardedFailure = /\|\|\s*(?:exit|return|false)\b/.test(statement);
  if (statement.includes('||') && !guardedFailure) return null;
  const words = shellWords(statement).map((word) => word.replace(/^[!({]+/, '').replace(/[)}]+$/, '')).filter(Boolean);
  let index = 0;
  while (/^[A-Za-z_][A-Za-z0-9_]*=/.test(words[index] || '')) index += 1;
  const exec = words[index] === 'exec';
  if (exec) index += 1;
  const executable = path.basename(words[index] || '');
  const direct = executable === 'notify-push';
  const subcommand = /no[-_]?mistakes/i.test(executable) && words[index + 1] === 'notify-push';
  if (!direct && !subcommand) return null;
  const args = words.slice(index + (direct ? 1 : 2));
  if (!args.some((arg) => arg === '--gate' || arg.startsWith('--gate='))) return null;
  return { exec, guardedFailure };
}

function hasReachableNotifyPush(text) {
  const statements = hookStatements(text);
  let errexit = false;
  let terminated = false;
  const controls = [];
  for (const [index, statement] of statements.entries()) {
    const words = shellWords(statement);
    const first = words[0] || '';
    if (first === 'fi' || first === 'done') {
      controls.pop();
      continue;
    }
    if (first === 'else' && controls.length) {
      const current = controls.at(-1);
      if (current.known) current.reachable = !current.reachable;
      continue;
    }
    if (first === 'if') {
      const condition = words[1] === 'false' || (words[1] === '!' && words[2] === 'true')
        ? false
        : words[1] === 'true' || (words[1] === '!' && words[2] === 'false')
          ? true
          : null;
      controls.push({ known: condition !== null, reachable: condition !== false });
      continue;
    }
    if (['while', 'until'].includes(first)) {
      const condition = words[1] === 'false' ? first === 'until' : words[1] === 'true' ? first === 'while' : null;
      controls.push({ known: condition !== null, reachable: condition !== false });
      continue;
    }
    if (terminated || controls.some((control) => !control.reachable)) continue;
    if (words[0] === 'set') {
      if (words.some((word) => /^-[a-z]*e[a-z]*$/i.test(word))) errexit = true;
      if (words.some((word) => /^\+[a-z]*e[a-z]*$/i.test(word))) errexit = false;
    }
    if (['exit', 'return'].includes(words[0])) {
      terminated = true;
      continue;
    }
    const invocation = notifyPushInvocation(statement);
    if (!invocation) continue;
    const laterExecutable = statements.slice(index + 1).some((candidate) => {
      const first = shellWords(candidate)[0] || '';
      return first && !['done', 'fi', 'esac'].includes(first);
    });
    if (invocation.exec || invocation.guardedFailure || errexit || !laterExecutable) return true;
  }
  return false;
}

export function hasNoMistakesPostReceiveHook(gatePath) {
  const hookPath = path.join(gatePath, 'hooks', 'post-receive');
  try {
    const stat = fs.statSync(hookPath);
    const text = fs.readFileSync(hookPath, 'utf8');
    return stat.isFile() && (stat.mode & 0o111) !== 0 && hasReachableNotifyPush(text);
  } catch {
    return false;
  }
}

export function isOwnedNoMistakesGate(gatePath, options = {}) {
  const bare = run('git', ['-C', gatePath, 'rev-parse', '--is-bare-repository'], options);
  return bare.status === 0 && bare.stdout.trim() === 'true' && hasNoMistakesPostReceiveHook(gatePath);
}

export function repairGateHook(gatePath, options = {}) {
  const hookPath = path.join(gatePath, 'hooks', 'post-receive');
  if (!isOwnedNoMistakesGate(gatePath, options)) return { status: 'untrusted', hookPath };
  if (!fs.existsSync(hookPath)) return { status: 'skipped', hookPath };
  const original = fs.readFileSync(hookPath, 'utf8');
  const repaired = repairHookText(original);
  if (!repaired.changed) return { status: 'clean', hookPath };
  fs.writeFileSync(hookPath, repaired.text);
  fs.chmodSync(hookPath, 0o755);
  return { status: 'repaired', hookPath };
}

function effectivePrePushPath(repo) {
  const result = run('git', ['-C', repo, 'rev-parse', '--git-path', 'hooks/pre-push']);
  if (result.status !== 0 || !result.stdout.trim()) return '';
  const candidate = result.stdout.trim();
  return path.isAbsolute(candidate) ? candidate : path.resolve(repo, candidate);
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

export function synchronizeGatePrePushHook(repo, gatePath, options = {}) {
  const sourcePath = effectivePrePushPath(repo);
  const targetPath = path.join(gatePath, 'hooks', 'pre-push');
  if (!isOwnedNoMistakesGate(gatePath, options)) return { status: 'untrusted', sourcePath, targetPath };
  if (!sourcePath || !fs.existsSync(sourcePath)) return { status: 'skipped', sourcePath, targetPath };
  const sourceStat = fs.statSync(sourcePath);
  if (!sourceStat.isFile() || (sourceStat.mode & 0o111) === 0) return { status: 'skipped', sourcePath, targetPath };
  if (path.resolve(sourcePath) === path.resolve(targetPath)) return { status: 'clean', sourcePath, targetPath };

  const dispatcher = [
    '#!/bin/sh',
    dispatcherMarker,
    `# source: ${JSON.stringify(sourcePath)}`,
    `exec ${shellQuote(sourcePath)} "$@"`,
    '',
  ].join('\n');
  const targetMatches = fs.existsSync(targetPath)
    && fs.statSync(targetPath).isFile()
    && (fs.statSync(targetPath).mode & 0o111) !== 0
    && fs.readFileSync(targetPath, 'utf8') === dispatcher;
  if (targetMatches) return { status: 'clean', sourcePath, targetPath };

  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  const tempPath = `${targetPath}.tmp-${process.pid}`;
  try {
    fs.writeFileSync(tempPath, dispatcher, { mode: 0o755 });
    fs.chmodSync(tempPath, 0o755);
    fs.renameSync(tempPath, targetPath);
  } finally {
    fs.rmSync(tempPath, { force: true });
  }
  return { status: 'synchronized', sourcePath, targetPath };
}

function parseArgs(argv) {
  if (argv[0] === '--gate') return { gate: argv[1] || '' };
  return { repo: argv[0] || process.cwd() };
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const repo = options.repo ? path.resolve(options.repo) : '';
  const gatePath = options.gate ? path.resolve(options.gate) : resolveGatePath(repo);
  if (!gatePath) {
    console.log('no-mistakes-gate-hook: skipped');
    return;
  }
  if (!isOwnedNoMistakesGate(gatePath)) {
    console.error(`no-mistakes-gate-hook: untrusted gate ${gatePath}`);
    process.exitCode = 1;
    return;
  }
  const postReceive = repairGateHook(gatePath);
  const prePush = repo ? synchronizeGatePrePushHook(repo, gatePath) : { status: 'skipped' };
  console.log(`no-mistakes-gate-hook: post-receive=${postReceive.status} pre-push=${prePush.status}`);
}

function comparablePath(file) {
  try {
    return fs.realpathSync(file);
  } catch {
    return path.resolve(file);
  }
}

if (process.argv[1] && comparablePath(process.argv[1]) === comparablePath(fileURLToPath(import.meta.url))) {
  main();
}
