import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { identityHash } from './crypto.mjs';

export function git(cwd, args, options = {}) {
  try {
    return execFileSync('git', ['-C', cwd, ...args], {
      encoding: options.encoding ?? 'utf8',
      maxBuffer: options.maxBuffer ?? 16 * 1024 * 1024,
      stdio: ['ignore', 'pipe', options.quiet ? 'ignore' : 'pipe'],
    });
  } catch (error) {
    if (options.allowFailure) return null;
    const detail = error.stderr?.toString().trim();
    throw new Error(detail ? `Git failed: ${detail}` : `Git failed: ${args.join(' ')}`);
  }
}

function absoluteGitPath(cwd, value) {
  const trimmed = value.trim();
  return fs.realpathSync(path.isAbsolute(trimmed) ? trimmed : path.resolve(cwd, trimmed));
}

export function resolveGitIdentity(cwd) {
  const commonRaw = git(cwd, ['rev-parse', '--path-format=absolute', '--git-common-dir']);
  const topRaw = git(cwd, ['rev-parse', '--path-format=absolute', '--show-toplevel']);
  const gitDirRaw = git(cwd, ['rev-parse', '--path-format=absolute', '--git-dir']);
  const commonDir = absoluteGitPath(cwd, commonRaw);
  const checkoutRoot = absoluteGitPath(cwd, topRaw);
  const gitDir = absoluteGitPath(cwd, gitDirRaw);
  const repoId = identityHash(`git-common\0${commonDir}`);
  const checkoutId = identityHash(`checkout\0${repoId}\0${checkoutRoot}\0${gitDir}`);
  return { commonDir, checkoutRoot, gitDir, repoId, checkoutId };
}
