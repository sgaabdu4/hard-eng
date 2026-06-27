#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cron-trust-'));
const fakeBin = path.join(tmp, 'bin');
const currentCron = path.join(tmp, 'current-cron');
const outputCron = path.join(tmp, 'output-cron');
const home = path.join(tmp, 'home');
const pathValue = `/opt/homebrew/bin:/usr/local/bin:${home}/.npm-global/bin:${home}/.local/bin:${home}/flutter/bin:${home}/.pub-cache/bin:/usr/bin:/bin:/usr/sbin:/sbin`;
const autoSyncJob = `*/15 * * * * cd "${repo}" && PATH="${pathValue}" "${repo}/scripts/auto-sync.sh" >> "${repo}/.git/auto-sync.log" 2>&1`;
fs.mkdirSync(fakeBin, { recursive: true });

fs.writeFileSync(path.join(fakeBin, 'crontab'), [
  '#!/usr/bin/env bash',
  'set -euo pipefail',
  'if [[ "${1:-}" == "-l" ]]; then',
  '  if [[ -f "${HARD_ENG_FAKE_CRON_CURRENT:-}" ]]; then cat "$HARD_ENG_FAKE_CRON_CURRENT"; exit 0; fi',
  '  exit 1',
  'fi',
  'cp "$1" "$HARD_ENG_FAKE_CRON_OUT"',
  '',
].join('\n'));
fs.chmodSync(path.join(fakeBin, 'crontab'), 0o755);

function runCron(overrides = {}) {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (key.startsWith('HARD_ENG_')) delete env[key];
  }
  const result = spawnSync('bash', [path.join(repo, 'scripts', 'install-cron.sh')], {
    cwd: repo,
    env: {
      ...env,
      HOME: home,
      PATH: `${fakeBin}:${process.env.PATH}`,
      HARD_ENG_FAKE_CRON_CURRENT: currentCron,
      HARD_ENG_FAKE_CRON_OUT: outputCron,
      ...overrides,
    },
    encoding: 'utf8',
    timeout: 30000,
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return fs.readFileSync(outputCron, 'utf8');
}

fs.writeFileSync(currentCron, [
  '# BEGIN hard-eng auto-sync',
  autoSyncJob,
  '# END hard-eng auto-sync',
  '# BEGIN hard-eng codex-stack-update',
  '* * * * * old codex-update-stack',
  '# END hard-eng codex-stack-update',
  '',
].join('\n'));
const safeCron = runCron();
assert.match(safeCron, /# BEGIN hard-eng auto-sync/);
assert.doesNotMatch(safeCron, /codex-stack-update|codex-update-stack/);

fs.writeFileSync(currentCron, '');
const trustedCron = runCron({ HARD_ENG_TRUSTED_WORKSTATION: '1' });
assert.match(trustedCron, /# BEGIN hard-eng codex-stack-update/);
assert.match(trustedCron, /HARD_ENG_TRUSTED_WORKSTATION=1 PATH=/);
assert.match(trustedCron, /codex-update-stack/);

console.log('install-cron-trust-test: pass');
