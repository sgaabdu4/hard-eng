#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let json = false;
let requireNoMistakesRemote = true;

for (const arg of args) {
  if (arg === '--json') json = true;
  else if (arg === '--allow-missing-no-mistakes-remote') requireNoMistakesRemote = false;
  else if (arg === '--help' || arg === '-h') {
    console.log(`Usage: check-no-mistakes-projects.mjs [--json] [--allow-missing-no-mistakes-remote] [repo]

    Inventories Git project roots under a repo and verifies each configured
    non-vendor project has no-mistakes config, a no-mistakes remote, active
    hook readiness, and deterministic project quality gates.
    Use --allow-missing-no-mistakes-remote for generic CI lanes that cannot
    rely on local no-mistakes init state.`);
    process.exit(0);
  } else {
    root = path.resolve(arg);
  }
}

root = path.resolve(root);
const scriptDir = path.dirname(new URL(import.meta.url).pathname);
const ensureWorktreeReady = path.join(scriptDir, 'ensure-worktree-ready.sh');
const projectQualityGates = path.join(scriptDir, 'check-project-quality-gates.mjs');

const ignoredDirectoryNames = new Set([
  '.cache',
  '.codebase',
  '.codebase-memory',
  '.git',
  'backups',
  'coverage',
  'dist',
  'node_modules',
  'outputs',
  'target',
  'tmp',
  'vendor',
]);

function run(command, commandArgs, cwd = root) {
  const result = spawnSync(command, commandArgs, { cwd, encoding: 'utf8' });
  return {
    status: result.status ?? 1,
    stdout: result.stdout.trim(),
    stderr: result.stderr.trim(),
  };
}

function isGitCheckout(repo) {
  return run('git', ['-C', repo, 'rev-parse', '--show-toplevel']).status === 0;
}

function gitOutput(repo, gitArgs) {
  const result = run('git', ['-C', repo, ...gitArgs]);
  return result.status === 0 ? result.stdout : '';
}

function trackedSubmodulePaths(repo) {
  const output = gitOutput(repo, ['ls-files', '-s']);
  const paths = new Set();
  for (const line of output.split('\n')) {
    const match = line.match(/^160000\s+\S+\s+\d+\t(.+)$/);
    if (match) paths.add(match[1].replaceAll('\\', '/'));
  }
  return paths;
}

function collectNestedGitRoots(repo, dir = '', depth = 0, out = []) {
  if (depth > 7 || out.length > 500) return out;
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(repo, dir), { withFileTypes: true });
  } catch {
    return out;
  }
  const hasGitMarker = entries.some((entry) => entry.name === '.git' && (entry.isDirectory() || entry.isFile()));
  if (dir && hasGitMarker) {
    out.push(dir.split(path.sep).join('/'));
    return out;
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || ignoredDirectoryNames.has(entry.name)) continue;
    collectNestedGitRoots(repo, path.join(dir, entry.name), depth + 1, out);
  }
  return out;
}

function checkRepo(repo, relativePath, type) {
  const configPath = path.join(repo, '.no-mistakes.yaml');
  const hasNoMistakesConfig = fs.existsSync(configPath);
  const noMistakesRemote = gitOutput(repo, ['remote', 'get-url', 'no-mistakes']);
  const hookReady = run(ensureWorktreeReady, ['--check', '--require-pre-push', repo]);
  const qualityGate = run(process.execPath, [projectQualityGates, '--require-push-gate', repo]);
  return {
    path: relativePath,
    type,
    hasNoMistakesConfig,
    hasNoMistakesRemote: Boolean(noMistakesRemote),
    hookReady: hookReady.status === 0,
    qualityGate: qualityGate.status === 0,
    hookReadyError: hookReady.status === 0 ? '' : hookReady.stderr || hookReady.stdout,
    qualityGateError: qualityGate.status === 0 ? '' : qualityGate.stderr || qualityGate.stdout,
  };
}

function hasNoMistakesConfig(repo) {
  return fs.existsSync(path.join(repo, '.no-mistakes.yaml'));
}

const blockers = [];
const warnings = [];
const repos = [];

if (!isGitCheckout(root)) {
  warnings.push(`${root} is not a Git checkout`);
} else {
  const submodules = trackedSubmodulePaths(root);
  repos.push(checkRepo(root, '.', 'root'));
  for (const rel of collectNestedGitRoots(root)) {
    const nestedRoot = path.join(root, rel);
    const type = submodules.has(rel)
      ? 'tracked-submodule'
      : hasNoMistakesConfig(nestedRoot)
        ? 'project'
        : 'unmanaged-nested';
    repos.push(type === 'project' ? checkRepo(nestedRoot, rel, type) : { path: rel, type });
    if (type === 'unmanaged-nested') {
      blockers.push(`unmanaged nested Git repo ${rel}; add .no-mistakes.yaml and initialize no-mistakes, move it outside this repo, or convert it to a tracked submodule`);
    }
  }
}

for (const repo of repos) {
  if (!['root', 'project'].includes(repo.type)) continue;
  if (!repo.hasNoMistakesConfig) blockers.push(`${repo.path} must define .no-mistakes.yaml`);
  if (requireNoMistakesRemote && !repo.hasNoMistakesRemote) blockers.push(`${repo.path} must be initialized with no-mistakes init`);
  if (!repo.hookReady) blockers.push(`${repo.path} worktree hooks are not ready: ${repo.hookReadyError}`);
  if (!repo.qualityGate) blockers.push(`${repo.path} project quality gate failed: ${repo.qualityGateError}`);
}

const result = { root, repos, blockers, warnings };

if (json) {
  console.log(`${JSON.stringify(result, null, 2)}\n`);
} else {
  console.log(`no-mistakes-projects: ${blockers.length ? 'fail' : 'pass'}`);
  for (const repo of repos) console.log(`${repo.type}: ${repo.path}`);
  for (const warning of warnings) console.log(`warning: ${warning}`);
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
}

process.exit(blockers.length ? 1 : 0);
