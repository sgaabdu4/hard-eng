import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectLegacyControlPlane } from '../../runtime/lib/legacy-control-plane.mjs';

function home(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test('legacy control-plane inventory is bounded and passes only when native owners are resolved', () => {
  const targetHome = home('hard-eng-control-plane-clean-');
  const clean = inspectLegacyControlPlane(targetHome, { cronText: '' });
  assert.equal(clean.status, 'PASS');
  assert.equal(clean.managed_bins.present, 0);
  assert.equal(clean.launch_agent.status, 'ABSENT');
  assert.equal(clean.crontab.status, 'PASS');
  assert.equal(clean.treehouse.present, false);
  assert.match(clean.evidence_digest, /^[a-f0-9]{64}$/);

  const bin = path.join(targetHome, '.codex', 'bin');
  fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'codex-watchdog'), [
    '#!/bin/sh', '# Managed by hard-eng installer.', 'PRIVATE_FIXTURE_COMMAND', '',
  ].join('\n'));
  const blocked = inspectLegacyControlPlane(targetHome, { cronText: '' });
  assert.equal(blocked.status, 'BLOCKED');
  assert.equal(blocked.managed_bins.owned, 1);
  assert.equal(blocked.blockers.some((item) => item.code === 'LEGACY_MANAGED_BIN_PRESENT'), true);
  assert.equal(JSON.stringify(blocked).includes('PRIVATE_FIXTURE_COMMAND'), false);
});

test('launchd, cron, and Treehouse block cutover while external no-mistakes is preserved', () => {
  const targetHome = home('hard-eng-control-plane-blockers-');
  const launchAgent = path.join(targetHome, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist');
  fs.mkdirSync(path.dirname(launchAgent), { recursive: true });
  fs.writeFileSync(launchAgent, [
    '<string>dev.hard-eng.codex-watchdog</string>',
    '<string>/Users/fixture/.codex/bin/codex-watchdog</string>',
  ].join('\n'));
  fs.mkdirSync(path.join(targetHome, '.local', 'bin'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.local', 'bin', 'treehouse'), 'external treehouse bytes\n');
  fs.mkdirSync(path.join(targetHome, '.treehouse'));
  fs.writeFileSync(path.join(targetHome, '.local', 'bin', 'no-mistakes'), 'PRIVATE_NO_MISTAKES_BYTES\n');
  fs.mkdirSync(path.join(targetHome, '.no-mistakes'));

  const report = inspectLegacyControlPlane(targetHome, {
    cronText: [
      '# .codex/bin/codex-watchdog is only a comment',
      '*/5 * * * * "$HOME/.codex/bin/codex-watchdog"',
      '0 0 * * * unrelated-command',
    ].join('\n'),
  });
  assert.equal(report.status, 'BLOCKED');
  assert.equal(report.launch_agent.status, 'OWNED_BLOCKER');
  assert.equal(report.crontab.matching_entries, 1);
  assert.equal(report.treehouse.binary_type, 'file');
  assert.equal(report.treehouse.state_type, 'directory');
  assert.deepEqual(report.external_no_mistakes, {
    binary_type: 'file',
    state_type: 'directory',
    preserved: true,
  });
  assert.equal(JSON.stringify(report).includes('*/5'), false);
  assert.equal(JSON.stringify(report).includes('PRIVATE_NO_MISTAKES_BYTES'), false);
});

test('unknown crontab state and modified legacy surfaces fail closed', () => {
  const targetHome = home('hard-eng-control-plane-unknown-');
  const bin = path.join(targetHome, '.codex', 'bin');
  fs.mkdirSync(bin, { recursive: true });
  fs.writeFileSync(path.join(bin, 'codex-health'), 'unowned bytes\n');
  const report = inspectLegacyControlPlane(targetHome, { cronText: null });
  assert.equal(report.status, 'BLOCKED');
  assert.equal(report.crontab.status, 'UNKNOWN');
  assert.equal(report.managed_bins.modified, 1);
  assert.equal(report.blockers.some((item) => item.code === 'CRONTAB_INVENTORY_UNAVAILABLE'), true);
  assert.equal(report.blockers.some((item) => item.code === 'MODIFIED_LEGACY_SURFACE'), true);
});
