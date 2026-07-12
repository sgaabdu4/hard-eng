import fs from 'node:fs';
import path from 'node:path';
import { git } from './git.mjs';
import { resolveContainedPath } from './safe-path.mjs';

const globPattern = /[*?\[\]{}!]/;
const forbiddenParts = new Set(['.git', '.codex', 'node_modules', 'build', 'dist', 'target', '.dart_tool', '.cache', 'coverage']);
const secretPath = /(?:^|\/)(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|[^/]*\.(?:pem|key|p12)|credentials?(?:\.[^/]*)?|secrets?(?:\.[^/]*)?)$/i;

function includeEntries(repo) {
  const file = path.join(repo, '.worktreeinclude');
  if (!fs.existsSync(file)) return [];
  if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) throw new Error('.worktreeinclude must be a regular tracked file.');
  if (git(repo, ['ls-files', '--error-unmatch', '--', '.worktreeinclude'], { allowFailure: true, quiet: true }) === null) {
    throw new Error('.worktreeinclude must be tracked before it can own worktree inputs.');
  }
  return fs.readFileSync(file, 'utf8').split(/\r?\n/)
    .map((line) => line.trim()).filter((line) => line && !line.startsWith('#'));
}

function inspectDirectory(root, relativeRoot, limit = 200) {
  const pending = [{ directory: root, relative: relativeRoot }];
  let entries = 0;
  while (pending.length) {
    const { directory, relative } = pending.pop();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      entries += 1;
      if (entries > limit) throw new Error('directory exceeds bounded inventory');
      const target = path.join(directory, entry.name);
      const relativeTarget = path.posix.join(relative, entry.name);
      const stat = fs.lstatSync(target);
      if (stat.isSymbolicLink() || stat.isSocket() || (!stat.isFile() && !stat.isDirectory())) throw new Error('directory contains an unsafe entry');
      if (secretPath.test(relativeTarget)) return { secret_descendant: true, forbidden_descendant: false };
      if (forbiddenParts.has(entry.name)) return { secret_descendant: false, forbidden_descendant: true };
      if (stat.isDirectory()) pending.push({ directory: target, relative: relativeTarget });
    }
  }
  return { secret_descendant: false, forbidden_descendant: false };
}

function inspectOne(repo, relative) {
  const base = { path: relative, status: 'FAIL', classification: 'invalid', approval_required: false, source_type: null };
  if (
    typeof relative !== 'string'
    || !relative
    || path.isAbsolute(relative)
    || relative.includes('\\')
    || globPattern.test(relative)
    || relative.split('/').includes('..')
    || relative === '.'
  ) return base;
  const normalized = path.posix.normalize(relative);
  const parts = normalized.split('/');
  if (normalized !== relative || parts.some((part) => forbiddenParts.has(part))) return base;
  let target;
  try {
    target = resolveContainedPath(repo, relative, { label: 'Worktree input' }).target;
  } catch {
    return { ...base, classification: 'unsafe-source-path' };
  }
  const tracked = git(repo, ['ls-files', '--error-unmatch', '--', relative], { allowFailure: true, quiet: true }) !== null;
  if (tracked) return { ...base, classification: 'tracked-input-not-needed' };
  const ignored = git(repo, ['check-ignore', '-q', '--', relative], { allowFailure: true, quiet: true }) !== null;
  if (!ignored) return { ...base, classification: 'not-ignored' };
  const stat = fs.lstatSync(target);
  if (stat.isSymbolicLink() || stat.isSocket() || (!stat.isFile() && !stat.isDirectory())) return { ...base, classification: 'unsafe-source-type' };
  if (stat.isDirectory()) {
    try {
      const inventory = inspectDirectory(target, relative);
      if (inventory.secret_descendant) return { ...base, classification: 'secret-descendant-must-be-explicit' };
      if (inventory.forbidden_descendant) return { ...base, classification: 'forbidden-directory-descendant' };
    } catch {
      return { ...base, classification: 'unsafe-directory' };
    }
  }
  const approvalRequired = secretPath.test(relative);
  return {
    path: relative,
    status: approvalRequired ? 'CONCERNS' : 'PASS',
    classification: approvalRequired ? 'secret-local-input' : 'ignored-local-input',
    approval_required: approvalRequired,
    source_type: stat.isDirectory() ? 'directory' : 'file',
  };
}

export function diagnoseWorktree(repo, { requested = [] } = {}) {
  const entries = [...new Set([...includeEntries(repo), ...requested])].map((relative) => inspectOne(repo, relative));
  const status = entries.some((entry) => entry.status === 'FAIL')
    ? 'FAIL'
    : entries.some((entry) => entry.status === 'CONCERNS') ? 'CONCERNS' : 'PASS';
  return {
    status,
    mode: 'worktree',
    entries,
    warning: entries.some((entry) => entry.approval_required)
      ? 'Codex copies this exact secret-bearing input into every Codex-managed worktree; explicit approval is required before adding the path to .worktreeinclude.'
      : null,
    copy_owner: 'codex-managed-worktree',
    mutation: 'performed-by-codex-at-worktree-creation',
  };
}
