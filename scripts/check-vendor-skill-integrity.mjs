#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const root = path.resolve(process.argv[2] || '.');
const vendorRoot = path.join(root, 'vendor', 'skill-upstreams');
const failures = [];
const localGitEnv = spawnSync('git', ['rev-parse', '--local-env-vars'], {
  cwd: root,
  encoding: 'utf8',
}).stdout.split('\n').filter(Boolean);
const gitEnv = { ...process.env };
for (const name of localGitEnv) delete gitEnv[name];

function git(args, cwd = root) {
  return spawnSync('git', args, { cwd, encoding: 'utf8', env: gitEnv });
}

function realpath(target) {
  try {
    return fs.realpathSync.native(target);
  } catch {
    return path.resolve(target);
  }
}

function fail(message) {
  failures.push(message);
}

function modeFromLsFiles(file) {
  const ls = git(['ls-files', '-s', '--', file]);
  return ls.stdout.trim().split(/\s+/)[0] || '';
}

function modeFromHead(file) {
  const tree = git(['ls-tree', 'HEAD', '--', file]);
  return tree.stdout.trim().split(/\s+/)[0] || '';
}

if (!fs.existsSync(vendorRoot)) {
  fail('vendor/skill-upstreams is missing');
} else {
  for (const entry of fs.readdirSync(vendorRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const submodule = path.join(vendorRoot, entry.name);
    if (!fs.existsSync(path.join(submodule, '.git'))) continue;
    const topLevel = git(['rev-parse', '--show-toplevel'], submodule);
    if (topLevel.status !== 0) {
      fail(`cannot inspect vendored skill upstream ${path.relative(root, submodule)}`);
      continue;
    }
    if (realpath(topLevel.stdout.trim()) !== realpath(submodule)) continue;
    const status = git(['status', '--porcelain=v1', '--untracked-files=all'], submodule);
    if (status.status !== 0) {
      fail(`cannot inspect vendored skill upstream ${path.relative(root, submodule)}`);
      continue;
    }
    if (status.stdout.trim()) {
      fail(`dirty vendored skill upstream ${path.relative(root, submodule)}:\n${status.stdout.trim()}`);
    }
  }
}

for (const mode of ['--cached', '']) {
  const args = ['diff', '--name-only', '--diff-filter=ACMRD'];
  if (mode) args.splice(1, 0, mode);
  args.push('--', 'vendor/skill-upstreams');
  const diff = git(args);
  if (diff.status !== 0) {
    fail(`cannot inspect ${mode ? 'staged ' : ''}vendor changes`);
    continue;
  }
  for (const file of diff.stdout.split('\n').filter(Boolean)) {
    const currentMode = modeFromLsFiles(file);
    const headMode = modeFromHead(file);
    if (currentMode !== '160000' && headMode !== '160000') {
      fail(`repo-owned vendored skill file changed: ${file}`);
    }
  }
}

if (failures.length) {
  console.error(`vendor-skill-integrity: ${failures.length} failure(s)`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log('vendor-skill-integrity: pass');
