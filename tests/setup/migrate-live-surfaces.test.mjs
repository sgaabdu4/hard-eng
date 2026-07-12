import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makePluginClient } from '../fixtures/plugin-client-fixture.mjs';
import { inspectLegacySurfaces } from '../../plugins/hard-eng/runtime/lib/setup-migration.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const pluginClient = makePluginClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { ...options, pluginClient });
}

function fixtureHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-migrate-home-'));
  fs.mkdirSync(path.join(home, '.agents', 'skills', 'legacy-skill'), { recursive: true });
  fs.mkdirSync(path.join(home, '.agents', 'codex'), { recursive: true });
  fs.writeFileSync(path.join(home, '.agents', 'codex', 'hooks.json'), '{}\n');
  fs.writeFileSync(path.join(home, '.agents', 'mcp-config.json'), '{}\n');
  fs.mkdirSync(path.join(home, '.codex', 'skills'), { recursive: true });
  fs.mkdirSync(path.join(home, '.codex', 'agents'), { recursive: true });
  fs.symlinkSync(path.join(home, '.agents', 'AGENTS.md'), path.join(home, '.codex', 'AGENTS.md'));
  fs.symlinkSync(path.join(home, '.agents', 'codex', 'hooks.json'), path.join(home, '.codex', 'hooks.json'));
  fs.symlinkSync(path.join(home, '.agents', 'mcp-config.json'), path.join(home, '.codex', 'mcp-config.json'));
  fs.unlinkSync(path.join(home, '.agents', 'mcp-config.json'));
  fs.symlinkSync(path.join(home, '.agents', 'AGENTS.md'), path.join(home, '.codex', 'AGENTS.md.backup.20260712000000'));
  fs.symlinkSync(path.join(home, 'personal-agents.md'), path.join(home, '.codex', 'AGENTS.md.backup.20260712000001'));
  fs.symlinkSync(path.join(home, '.agents', 'skills', 'legacy-skill'), path.join(home, '.codex', 'skills', 'legacy-skill'));
  fs.writeFileSync(path.join(home, '.codex', 'agents', 'worker.toml'), '# hard-eng-managed-agent/v1\nmodel = "legacy"\n');
  fs.writeFileSync(path.join(home, '.codex', 'agents', 'staff-engineer.toml'), 'model = "user-modified"\n');
  fs.writeFileSync(path.join(home, '.codex', 'agents', 'personal.toml'), 'model = "personal"\n');
  fs.writeFileSync(path.join(home, '.codex', 'auth.json'), '{"preserve":true}\n');
  fs.mkdirSync(path.join(home, '.codex', 'plugins', 'cache'), { recursive: true });
  fs.writeFileSync(path.join(home, '.codex', 'plugins', 'cache', 'preserve.txt'), 'preserve\n');
  fs.writeFileSync(path.join(home, '.codex', 'config.toml'), '[mcp_servers.context-mode]\n');
  return home;
}

function addLegacyRuntimeSurfaces(home) {
  fs.mkdirSync(path.join(home, '.codex', 'bin'), { recursive: true });
  fs.writeFileSync(
    path.join(home, '.codex', 'bin', 'codex-health'),
    '#!/bin/sh\n# Managed by hard-eng installer.\necho legacy\n',
    { mode: 0o755 },
  );
  fs.writeFileSync(
    path.join(home, '.codex', 'bin', 'codex-watchdog'),
    '#!/bin/sh\n# user modified watchdog\necho personal\n',
    { mode: 0o755 },
  );
  fs.mkdirSync(path.join(home, '.config', 'hard-eng'), { recursive: true });
  fs.writeFileSync(path.join(home, '.config', 'hard-eng', 'skills.json'), '{"selection":"all"}\n');
  const cache = path.join(home, '.cache', 'hard-eng', 'e2e-playwright');
  fs.mkdirSync(path.join(cache, 'node_modules', 'playwright'), { recursive: true });
  fs.mkdirSync(path.join(cache, 'node_modules', '.bin'), { recursive: true });
  fs.writeFileSync(path.join(cache, 'package.json'), '{"dependencies":{"playwright":"1.61.1"}}\n');
  fs.writeFileSync(path.join(cache, 'package-lock.json'), '{"name":"e2e-playwright","lockfileVersion":3}\n');
  fs.writeFileSync(path.join(cache, 'node_modules', 'playwright', 'index.js'), 'module.exports = {};\n');
  fs.symlinkSync('../playwright/index.js', path.join(cache, 'node_modules', '.bin', 'playwright'));
  fs.writeFileSync(path.join(home, '.zshenv'), [
    'export BEFORE=1',
    '# BEGIN hard-eng bootstrap path',
    'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"',
    '# END hard-eng bootstrap path',
    'export AFTER=1',
    '',
  ].join('\n'));
  fs.mkdirSync(path.join(home, '.no-mistakes'), { recursive: true });
  fs.writeFileSync(path.join(home, '.no-mistakes', 'state.sqlite'), 'opaque-state');
  fs.mkdirSync(path.join(home, '.local', 'bin'), { recursive: true });
  fs.writeFileSync(path.join(home, '.local', 'bin', 'no-mistakes'), [
    '#!/usr/bin/env bash',
    '# Managed by hard-eng no-mistakes wrapper.',
    'exit 0',
    '',
  ].join('\n'), { mode: 0o755 });
  fs.writeFileSync(path.join(home, '.local', 'bin', 'treehouse'), 'treehouse fixture\n', { mode: 0o755 });
  fs.mkdirSync(path.join(home, '.treehouse'), { recursive: true });
  fs.writeFileSync(path.join(home, '.treehouse', 'treehouse-state.json'), '{}\n');
}

test('migrate classifies legacy surfaces but defers deletion until explicit live cutover', () => {
  const home = fixtureHome();
  const staged = runSetup(['migrate', '--home', home, '--dry-run'], { sourceRoot, now: NOW });
  assert.equal(staged.status, 'DRY_RUN');
  assert.ok(staged.legacy.every((entry) => entry.action === 'retain' || entry.action === 'defer'));
  assert.equal(fs.existsSync(path.join(home, '.codex', 'agents', 'worker.toml')), true);

  const live = runSetup(['migrate', '--home', home, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  const removedPaths = live.legacy.filter((entry) => entry.action === 'remove').map((entry) => entry.path);
  assert.ok(removedPaths.includes('.codex/hooks.json'));
  assert.ok(removedPaths.includes('.codex/mcp-config.json'));
  assert.ok(removedPaths.includes('.codex/skills/legacy-skill'));
  assert.ok(removedPaths.includes('.codex/agents/worker.toml'));
  assert.ok(removedPaths.includes('.codex/AGENTS.md.backup.20260712000000'));
  assert.ok(!removedPaths.includes('.codex/AGENTS.md.backup.20260712000001'));
  assert.ok(!removedPaths.includes('.codex/AGENTS.md'));
  assert.ok(!removedPaths.includes('.codex/agents/personal.toml'));
  assert.ok(!removedPaths.includes('.codex/agents/staff-engineer.toml'));
  assert.equal(live.legacy.find((entry) => entry.path === '.codex/agents/staff-engineer.toml').classification, 'unknown-or-modified-agent-profile');

  const applied = runSetup([
    'migrate', '--home', home, '--live-cutover', '--confirm', live.plan_digest,
  ], { sourceRoot, now: NOW });
  assert.equal(applied.status, 'PASS');
  assert.equal(fs.existsSync(path.join(home, '.codex', 'hooks.json')), false);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'mcp-config.json')), false);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'skills', 'legacy-skill')), false);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'agents', 'worker.toml')), false);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'AGENTS.md.backup.20260712000000')), false);
  assert.equal(fs.lstatSync(path.join(home, '.codex', 'AGENTS.md.backup.20260712000001')).isSymbolicLink(), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'AGENTS.md')), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'agents', 'personal.toml')), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'agents', 'staff-engineer.toml')), true);
  assert.equal(fs.readFileSync(path.join(home, '.codex', 'auth.json'), 'utf8'), '{"preserve":true}\n');
  assert.equal(fs.readFileSync(path.join(home, '.codex', 'plugins', 'cache', 'preserve.txt'), 'utf8'), 'preserve\n');
  assert.equal(fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8'), '[mcp_servers.context-mode]\n');
});

test('hash drift after approval cancels live migration without removing the changed file', () => {
  const home = fixtureHome();
  const dry = runSetup(['migrate', '--home', home, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  fs.writeFileSync(path.join(home, '.codex', 'agents', 'worker.toml'), 'model = "user-modified"\n');
  assert.throws(() => runSetup([
    'migrate', '--home', home, '--live-cutover', '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW }), /confirmation digest|changed after approval/i);
  assert.match(fs.readFileSync(path.join(home, '.codex', 'agents', 'worker.toml'), 'utf8'), /user-modified/);
});

test('migrate reports external retirements and refuses a blocked live cutover without partial cleanup', () => {
  const home = fixtureHome();
  addLegacyRuntimeSurfaces(home);

  const dry = runSetup(['migrate', '--home', home, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  const byPath = new Map(dry.legacy.map((entry) => [entry.path, entry]));
  assert.equal(byPath.get('.codex/bin/codex-health').action, 'remove');
  assert.equal(byPath.get('.codex/bin/codex-watchdog').action, 'retain');
  assert.equal(byPath.get('.config/hard-eng/skills.json').action, 'remove');
  assert.equal(byPath.get('.cache/hard-eng').action, 'remove');
  assert.equal(byPath.get('.zshenv').action, 'rewrite');
  assert.equal(byPath.get('.local/bin/no-mistakes').action, 'defer');
  assert.equal(byPath.get('.local/bin/treehouse').action, 'defer');
  assert.deepEqual(
    dry.migration_blockers.map((blocker) => blocker.code).sort(),
    [
      'MODIFIED_LEGACY_SURFACE',
      'NO_MISTAKES_EXTERNAL_DEPENDENCIES',
      'TREEHOUSE_RETIREMENT_REQUIRES_SEPARATE_APPROVAL',
    ],
  );
  assert.ok(dry.operations.some((operation) => operation.path === '.cache/hard-eng'));
  assert.ok(dry.operations.some((operation) => operation.path === '.zshenv' && operation.action === 'write'));

  assert.throws(() => runSetup([
    'migrate', '--home', home, '--live-cutover', '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW }), /live cutover is blocked/i);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'bin', 'codex-health')), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'bin', 'codex-watchdog')), true);
  assert.equal(fs.existsSync(path.join(home, '.config', 'hard-eng', 'skills.json')), true);
  assert.equal(fs.existsSync(path.join(home, '.cache', 'hard-eng')), true);
  const shell = fs.readFileSync(path.join(home, '.zshenv'), 'utf8');
  assert.match(shell, /hard-eng bootstrap path/);
  assert.match(shell, /\.npm-global\/bin/);
  assert.match(shell, /export BEFORE=1/);
  assert.match(shell, /export AFTER=1/);
  assert.equal(fs.existsSync(path.join(home, '.local', 'bin', 'no-mistakes')), true);
  assert.equal(fs.readFileSync(path.join(home, '.no-mistakes', 'state.sqlite'), 'utf8'), 'opaque-state');
  assert.equal(fs.existsSync(path.join(home, '.local', 'bin', 'treehouse')), true);
  assert.equal(fs.existsSync(path.join(home, '.treehouse', 'treehouse-state.json')), true);

  assert.equal(fs.existsSync(path.join(home, '.agents', 'plugins', 'hard-eng')), false);
});

test('unknown files inside the old cache and malformed shell blocks fail closed', () => {
  const cacheHome = fixtureHome();
  addLegacyRuntimeSurfaces(cacheHome);
  fs.writeFileSync(path.join(cacheHome, '.cache', 'hard-eng', 'personal.txt'), 'keep me\n');
  const cachePlan = runSetup(['migrate', '--home', cacheHome, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  const cacheEntry = cachePlan.legacy.find((entry) => entry.path === '.cache/hard-eng');
  assert.equal(cacheEntry.action, 'retain');
  assert.equal(cacheEntry.classification, 'unknown-or-modified-hard-eng-cache');

  const shellHome = fixtureHome();
  addLegacyRuntimeSurfaces(shellHome);
  fs.appendFileSync(path.join(shellHome, '.zshenv'), '# BEGIN hard-eng bootstrap path\n');
  const shellPlan = runSetup(['migrate', '--home', shellHome, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  const shellEntry = shellPlan.legacy.find((entry) => entry.path === '.zshenv');
  assert.equal(shellEntry.action, 'retain');
  assert.equal(shellEntry.classification, 'malformed-hard-eng-shell-block');
});

test('an interrupted directory retirement restores the cache and every earlier migration change', () => {
  const home = fixtureHome();
  addLegacyRuntimeSurfaces(home);
  fs.unlinkSync(path.join(home, '.codex', 'bin', 'codex-watchdog'));
  fs.rmSync(path.join(home, '.no-mistakes'), { recursive: true });
  fs.unlinkSync(path.join(home, '.local', 'bin', 'no-mistakes'));
  fs.rmSync(path.join(home, '.treehouse'), { recursive: true });
  fs.unlinkSync(path.join(home, '.local', 'bin', 'treehouse'));
  const beforeShell = fs.readFileSync(path.join(home, '.zshenv'), 'utf8');
  const dry = runSetup(['migrate', '--home', home, '--live-cutover', '--dry-run'], { sourceRoot, now: NOW });
  const cacheIndex = dry.operations.findIndex((operation) => operation.path === '.cache/hard-eng');
  assert.ok(cacheIndex >= 0);
  const failAfter = dry.operations
    .slice(0, cacheIndex + 1)
    .filter((operation) => operation.action !== 'noop').length;
  assert.throws(() => runSetup([
    'migrate', '--home', home, '--live-cutover', '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW, failAfter }), /injected transaction failure/i);
  assert.equal(fs.existsSync(path.join(home, '.cache', 'hard-eng', 'e2e-playwright', 'package.json')), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'bin', 'codex-health')), true);
  assert.equal(fs.readFileSync(path.join(home, '.zshenv'), 'utf8'), beforeShell);
});

test('marked Hard Eng cron commands are digest-only blockers until native retirement', () => {
  const home = fixtureHome();
  const cronText = [
    '*/5 * * * * /home/example/.agents/scripts/auto-sync.sh >/dev/null 2>&1',
    '0 1 * * * /home/example/personal-backup.sh',
    '',
  ].join('\n');
  const result = inspectLegacySurfaces(home, { cronText });
  const cron = result.legacy.find((entry) => entry.path === 'native:crontab');
  assert.equal(cron.classification, 'legacy-hard-eng-crontab-requires-native-retirement');
  assert.match(cron.current_hash, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(result).includes('/home/example'), false);
  assert.ok(result.blockers.some((blocker) => blocker.code === 'BACKGROUND_JOB_REQUIRES_MANUAL_RETIREMENT'));
});
