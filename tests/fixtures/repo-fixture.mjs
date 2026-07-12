import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

export function git(cwd, ...args) {
  return execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8' }).trim();
}

export function makeRepo(prefix = 'hard-eng-state-') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  git(root, 'init', '-q');
  git(root, 'config', 'user.name', 'Hard Eng Test');
  git(root, 'config', 'user.email', 'hard-eng@example.invalid');
  fs.writeFileSync(path.join(root, 'README.md'), '# Fixture\n');
  git(root, 'add', 'README.md');
  git(root, 'commit', '-qm', 'fixture');
  return root;
}

export function makeLinkedWorktree(repo) {
  const worktree = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-worktree-'));
  git(repo, 'worktree', 'add', '--detach', worktree, 'HEAD');
  return worktree;
}

export function mode(file) {
  return fs.statSync(file).mode & 0o777;
}
