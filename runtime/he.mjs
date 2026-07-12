#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { fingerprintCandidate } from './lib/candidate.mjs';
import { buildCheckRegistry, runCheckRegistry } from './lib/check-registry.mjs';
import { signCheckReceipt } from './lib/check-receipt.mjs';
import { runShipPreflight } from './lib/ship-preflight.mjs';
import { renderCapsule } from './lib/capsule.mjs';
import { renderPlanExcerpt, validatePlanFile } from './lib/plan.mjs';
import { diagnoseWorktree } from './lib/worktree.mjs';
import { listLocks, listRuns, listSessions, readKey, readRun, resolveStore } from './lib/store.mjs';
import { redactErrorMessage } from './lib/redact.mjs';

function parseArgs(argv) {
  const command = argv[0] ?? 'status';
  const options = {
    command, repo: process.cwd(), json: false, runId: null, sliceId: null, days: 30,
    dryRun: false, allowedUntracked: [], all: false, checkIds: [],
    worktree: false, worktreePaths: [],
  };
  for (let index = 1; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--repo') options.repo = path.resolve(argv[++index]);
    else if (value === '--run') options.runId = argv[++index];
    else if (value === '--slice') options.sliceId = argv[++index];
    else if (value === '--json') options.json = true;
    else if (value === '--days') options.days = Number.parseInt(argv[++index], 10);
    else if (value === '--dry-run') options.dryRun = true;
    else if (value === '--allow-untracked') options.allowedUntracked.push(argv[++index]);
    else if (value === '--all') options.all = true;
    else if (value === '--id') options.checkIds.push(argv[++index]);
    else if (value === '--worktree') options.worktree = true;
    else if (value === '--worktree-path') options.worktreePaths.push(argv[++index]);
    else throw new Error(`Unknown option: ${value}.`);
  }
  return options;
}

function summary(run) {
  return {
    run_id: run.run_id,
    phase: run.phase,
    cursor: run.cursor,
    revision: run.revision,
    updated_at: run.updated_at,
  };
}

function humanSummary(run) {
  return `${run.run_id}\t${run.phase}:${run.cursor.step}\trevision ${run.revision}`;
}

function doctor(repo) {
  let store;
  try {
    store = resolveStore(repo, { create: false });
  } catch (error) {
    return { status: 'FAIL', checks: [{ name: 'git-repository', status: 'FAIL', detail: error.message }] };
  }
  if (!store.exists) return { status: 'PASS', checks: [{ name: 'state-store', status: 'PASS', detail: 'not initialized' }] };
  const checks = [];
  for (const [name, target, expected] of [
    ['state-root-mode', store.root, 0o700],
    ['runs-mode', store.runsDir, 0o700],
    ['sessions-mode', store.sessionsDir, 0o700],
    ['locks-mode', store.locksDir, 0o700],
    ['key-mode', store.keyPath, 0o600],
  ]) {
    try {
      const actual = fs.statSync(target).mode & 0o777;
      checks.push({ name, status: actual === expected ? 'PASS' : 'FAIL', detail: actual.toString(8) });
    } catch {
      checks.push({ name, status: 'FAIL', detail: 'missing' });
    }
  }
  if (fs.existsSync(store.keyPath)) {
    checks.push({ name: 'key-length', status: fs.statSync(store.keyPath).size === 32 ? 'PASS' : 'FAIL', detail: `${fs.statSync(store.keyPath).size} bytes` });
  }
  for (const run of listRuns(store)) {
    checks.push({ name: `run:${run.run_id}`, status: 'PASS', detail: `${run.phase}:${run.cursor.step}@${run.revision}` });
  }
  for (const session of listSessions(store)) {
    if (session.pending) checks.push({
      name: `pending:${session.task_hash.slice(0, 12)}`,
      status: 'CONCERNS',
      detail: `${session.pending.action}; reconcile run ${session.run_id ?? 'unbound'} before retry`,
    });
  }
  for (const lock of listLocks(store)) {
    let alive = false;
    try {
      process.kill(lock.pid, 0);
      alive = true;
    } catch (error) {
      alive = error.code === 'EPERM';
    }
    checks.push({
      name: `lock:${lock.id}`,
      status: 'CONCERNS',
      detail: alive
        ? `active writer pid ${lock.pid}; never remove`
        : `stale writer pid ${lock.pid}; approve exact ${lock.id}.lock removal before repair`,
    });
  }
  const status = checks.some((check) => check.status === 'FAIL')
    ? 'FAIL'
    : checks.some((check) => check.status === 'CONCERNS') ? 'CONCERNS' : 'PASS';
  return { status, checks };
}

function pruneDryRun(store, days, now = Date.now()) {
  if (!Number.isInteger(days) || days < 1) throw new Error('--days must be a positive integer.');
  const cutoff = now - days * 24 * 60 * 60_000;
  return listRuns(store)
    .filter((run) => run.phase === 'Complete' && Date.parse(run.updated_at) < cutoff)
    .map(summary);
}

export function runCommand(argv, { now = Date.now(), onProgress = null } = {}) {
  const options = parseArgs(argv);
  if (options.command === 'doctor') {
    if (options.worktree) return diagnoseWorktree(options.repo, { requested: options.worktreePaths });
    return doctor(options.repo);
  }
  if (options.command === 'check') {
    const registry = buildCheckRegistry(options.repo);
    if (!options.all && options.checkIds.length === 0) throw new Error('check requires --all or at least one --id.');
    const selected = options.all ? registry : options.checkIds.map((id) => {
      const found = registry.find((check) => check.id === id);
      if (!found) throw new Error(`Unknown check ID: ${id}.`);
      return found;
    });
    return runCheckRegistry(options.repo, selected, { allowedUntracked: options.allowedUntracked, onProgress });
  }
  if (['plan-validate', 'plan-digest', 'plan-excerpt'].includes(options.command)) {
    if (!options.runId) throw new Error(`${options.command} requires --run <run-id>.`);
    const validation = validatePlanFile(options.repo, { runId: options.runId, requireAccepted: false });
    if (options.command === 'plan-validate') return validation;
    if (options.command === 'plan-digest') return validation.digest;
    if (!options.sliceId) throw new Error('plan-excerpt requires --slice <slice-id>.');
    return renderPlanExcerpt(fs.readFileSync(path.join(options.repo, 'plan.md'), 'utf8'), {
      runId: options.runId,
      sliceId: options.sliceId,
    });
  }
  const store = resolveStore(options.repo, { create: false });
  if (!store.exists) {
    if (['runs', 'status', 'prune'].includes(options.command)) return options.command === 'status' ? { status: 'uninitialized' } : [];
    throw new Error('Hard Eng state store is not initialized for this repository.');
  }
  if (options.command === 'runs') return listRuns(store).map(summary);
  if (options.command === 'ship') {
    if (!options.runId) throw new Error('ship requires --run <run-id>.');
    const run = readRun(store, options.runId);
    if (!run) throw new Error('Run not found.');
    const preflight = runShipPreflight(options.repo, run, { allowedUntracked: options.allowedUntracked });
    if (preflight.status !== 'PASS') return { status: 'FAIL', preflight, report: null, receipt: null };
    const report = runCheckRegistry(options.repo, buildCheckRegistry(options.repo), {
      allowedUntracked: options.allowedUntracked,
      onProgress,
    });
    if (report.status !== 'PASS') return { status: 'FAIL', preflight, report, receipt: null };
    return {
      status: 'PASS',
      preflight,
      report,
      receipt: signCheckReceipt(readKey(store), { run, report, preflight }, { now }),
    };
  }
  if (options.command === 'status') {
    if (!options.runId) throw new Error('Human status requires --run <run-id>; use he runs to list IDs.');
    const run = readRun(store, options.runId);
    if (!run) throw new Error('Run not found.');
    return {
      ...summary(run),
      next: run.next,
      capsule: renderCapsule(run),
      interruption: run.interruption ? {
        intent: run.interruption.intent,
        observed_result: run.interruption.observed_result,
        reconciliation_command: run.interruption.reconciliation_command,
      } : null,
    };
  }
  if (options.command === 'capsule') {
    if (!options.runId) throw new Error('Capsule requires --run <run-id>.');
    const run = readRun(store, options.runId);
    if (!run || run.phase === 'Complete') return '';
    return renderCapsule(run);
  }
  if (options.command === 'candidate') {
    return fingerprintCandidate(options.repo, { allowedUntracked: options.allowedUntracked });
  }
  if (options.command === 'prune') {
    if (!options.dryRun) throw new Error('Prune is proposal-only in v1; pass --dry-run.');
    return pruneDryRun(store, options.days, now);
  }
  throw new Error(`Unknown command: ${options.command}.`);
}

function printHuman(command, result) {
  if (typeof result === 'string') return result;
  if (command === 'runs' || command === 'prune') return result.length ? result.map(humanSummary).join('\n') : 'none';
  if (command === 'doctor') {
    if (result.mode === 'worktree') return [
      result.status,
      ...result.entries.map((entry) => `${entry.status}\t${entry.path}\t${entry.classification}`),
      ...(result.warning ? [result.warning] : []),
    ].join('\n');
    return [result.status, ...result.checks.map((check) => `${check.status}\t${check.name}\t${check.detail}`)].join('\n');
  }
  if (command === 'check') return [
    result.status,
    `candidate\t${result.candidate.fingerprint}`,
    ...result.results.map((entry) => `${entry.status}\t${entry.id}\t${entry.output_digest}`),
  ].join('\n');
  if (command === 'ship') return [
    result.status,
    result.report ? `candidate\t${result.report.candidate.fingerprint}` : 'candidate\tunavailable',
    result.receipt ? 'receipt\tavailable with --json' : 'receipt\tunavailable',
  ].join('\n');
  if (command === 'status' && result.run_id) return `${humanSummary(result)}\n${result.capsule}`;
  return JSON.stringify(result, null, 2);
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    const onProgress = options.json ? null : (event) => {
      const suffix = event.status ? ` ${event.status}` : '';
      process.stderr.write(`[${event.index}/${event.total}] ${event.id}${suffix}\n`);
    };
    const result = runCommand(process.argv.slice(2), { onProgress });
    process.stdout.write(`${options.json ? JSON.stringify(result) : printHuman(options.command, result)}\n`);
  } catch (error) {
    process.stderr.write(`${redactErrorMessage(error)}\n`);
    process.exitCode = 2;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
