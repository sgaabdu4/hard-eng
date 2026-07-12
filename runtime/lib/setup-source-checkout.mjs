import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { digestValue } from './canonical.mjs';

function git(sourceRoot, args) {
  const env = Object.fromEntries(
    [
      'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL',
      'SSH_AUTH_SOCK', 'GIT_SSH_COMMAND', 'GIT_ASKPASS',
    ]
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  );
  try {
    return execFileSync('git', ['-C', sourceRoot, ...args], {
      encoding: 'utf8',
      timeout: 30_000,
      maxBuffer: 1024 * 1024,
      env: { ...env, GIT_TERMINAL_PROMPT: '0' },
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch {
    throw new Error('Published self-hosted source checkout could not be observed exactly.');
  }
}

export function observePublishedSelfHostedSource({ home, sourceRoot }) {
  const homeRoot = fs.realpathSync(home);
  const expected = path.join(homeRoot, '.agents');
  if (!fs.existsSync(expected) || fs.realpathSync(sourceRoot) !== fs.realpathSync(expected)) return null;
  const stat = fs.lstatSync(expected);
  if (!stat.isDirectory() || stat.isSymbolicLink() || fs.realpathSync(sourceRoot) !== expected) {
    throw new Error('Published self-hosted source checkout is unsafe.');
  }
  if (fs.realpathSync(git(sourceRoot, ['rev-parse', '--show-toplevel'])) !== expected) {
    throw new Error('Published self-hosted source checkout root is invalid.');
  }
  if (git(sourceRoot, ['status', '--porcelain=v1', '--untracked-files=all'])) {
    throw new Error('Published self-hosted source checkout is dirty; setup adoption is blocked.');
  }
  const remotes = git(sourceRoot, ['remote']).split(/\r?\n/).filter(Boolean);
  const head = git(sourceRoot, ['rev-parse', 'HEAD']);
  const originMain = git(sourceRoot, ['rev-parse', 'refs/remotes/origin/main']);
  const upstream = git(sourceRoot, ['rev-parse', '--symbolic-full-name', '@{upstream}']);
  const remoteLines = git(sourceRoot, ['ls-remote', '--exit-code', 'origin', 'refs/heads/main'])
    .split(/\r?\n/).filter(Boolean);
  const [remoteHead, remoteRef] = remoteLines.length === 1 ? remoteLines[0].split(/\s+/) : [];
  if (
    remotes.length !== 1
    || remotes[0] !== 'origin'
    || !/^[a-f0-9]{40,64}$/i.test(head)
    || head !== originMain
    || head !== remoteHead
    || upstream !== 'refs/remotes/origin/main'
    || remoteRef !== 'refs/heads/main'
  ) throw new Error('Published self-hosted source checkout is not exact current origin/main.');
  const evidence = {
    schema: 'hard-eng/published-source-checkout/v1',
    status: 'PASS',
    clean: true,
    remote_count: 1,
    upstream: 'origin/main',
    head,
    origin_main: originMain,
    remote_head: remoteHead,
  };
  return { ...evidence, evidence_digest: digestValue(evidence) };
}

export function canAdoptPublishedSourceEntry({ sourceCheckout, sourceRoot, item, current, owned }) {
  return Boolean(
    sourceCheckout?.status === 'PASS'
    && owned
    && current
    && item.relative !== null
    && current.hash !== owned.installed_hash
    && current.type === item.expected_type
    && current.hash === item.hash
    && current.mode === item.mode
    && path.resolve(fs.realpathSync(sourceRoot), item.relative) === path.resolve(item.targetAbsolute)
  );
}
