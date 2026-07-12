import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup } from '../../scripts/setup.mjs';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import { createCodexCutoverClient } from '../../runtime/lib/codex-cutover.mjs';
import { APPROVED_CUTOVER_INVENTORY } from '../../runtime/lib/approved-cutover-inventory.mjs';
import { inspectSetupTarget } from '../../runtime/lib/setup-transaction.mjs';
import {
  fixtureRetirementInventory as buildFixtureRetirementInventory,
  seedApprovedLegacyLinks,
} from '../fixtures/cutover-inventory-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');

function installedHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-setup-cutover-'));
  const codex = path.join(home, '.codex');
  const cache = path.join(codex, 'plugins', 'cache', 'personal', 'hard-eng', '1.0.0');
  fs.mkdirSync(cache, { recursive: true });
  fs.chmodSync(path.join(codex, 'plugins', 'cache', 'personal', 'hard-eng'), 0o700);
  fs.chmodSync(cache, 0o700);
  fs.writeFileSync(path.join(cache, 'manifest.json'), '{"name":"hard-eng"}\n');
  fs.writeFileSync(path.join(codex, 'config.toml'), [
    'model = "gpt-test"',
    '[mcp_servers.unrelated]',
    'command = "unrelated"',
    '[plugins."hard-eng@personal"]',
    'enabled = true',
    '',
  ].join('\n'), { mode: 0o600 });
  seedApprovedLegacyLinks(home, APPROVED_CUTOVER_INVENTORY);
  fs.symlinkSync('/opt/external/skill', path.join(codex, 'skills', 'external'));
  fs.symlinkSync(path.join(home, '.agents', 'codex', 'hooks.json'), path.join(codex, 'hooks.json'));
  fs.symlinkSync(path.join('/private/tmp', `hard-eng-${path.basename(home)}`, 'mcp-config.json'), path.join(codex, 'mcp-config.json'));
  const teach = path.join(codex, 'skills', 'teach');
  fs.mkdirSync(teach);
  for (const name of APPROVED_CUTOVER_INVENTORY.duplicate_teach.files) {
    fs.writeFileSync(path.join(teach, name), `fixture ${name}\n`);
  }
  const agents = path.join(codex, 'agents');
  fs.mkdirSync(agents);
  for (const name of Object.keys(APPROVED_CUTOVER_INVENTORY.custom_agents)) {
    fs.writeFileSync(path.join(agents, name), `name = "${name}"\n`);
  }
  fs.writeFileSync(path.join(home, '.zshenv'), [
    'export KEEP_ME="yes"',
    '# BEGIN hard-eng bootstrap path',
    'export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"',
    '# END hard-eng bootstrap path',
    '',
  ].join('\n'));
  const e2eCache = path.join(home, '.cache', 'hard-eng', 'e2e-playwright');
  fs.mkdirSync(path.join(e2eCache, 'node_modules', 'playwright'), { recursive: true });
  fs.mkdirSync(path.join(e2eCache, 'node_modules', 'playwright-core'), { recursive: true });
  fs.writeFileSync(path.join(e2eCache, 'package.json'), '{}\n');
  fs.writeFileSync(path.join(e2eCache, 'package-lock.json'), '{}\n');
  fs.writeFileSync(path.join(e2eCache, 'node_modules', '.package-lock.json'), '{}\n');
  return home;
}

function fixtureRetirementInventory(home) {
  return buildFixtureRetirementInventory(home, APPROVED_CUTOVER_INVENTORY);
}

function retirementSnapshot(home) {
  return {
    agents: inspectSetupTarget(path.join(home, '.codex', 'agents')),
    teach: inspectSetupTarget(path.join(home, '.codex', 'skills', 'teach')),
    skill_links: Object.fromEntries(Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_skill_links)
      .map((name) => [name, inspectSetupTarget(path.join(home, '.codex', 'skills', name))])),
    backup_links: Object.fromEntries(Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_backup_links)
      .map((relative) => [relative, inspectSetupTarget(path.join(home, relative))])),
  };
}

function fakeCodex({ failAdd = false } = {}) {
  const calls = [];
  const state = { failAdd, failHome: null };
  function run(args, { home }) {
    calls.push({ args: [...args], home });
    const config = path.join(home, '.codex', 'config.toml');
    if (args.join(' ') === 'plugin remove hard-eng@personal --json') {
      const current = fs.readFileSync(config, 'utf8');
      fs.writeFileSync(config, current.replace('[plugins."hard-eng@personal"]\nenabled = true\n', ''));
      fs.rmSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng'), { recursive: true });
      return { status: 0, stdout: '{"removed":"hard-eng@personal"}', stderr: '', error: null };
    }
    if (args[0] === 'mcp' && args[1] === 'add') {
      if (state.failAdd && (!state.failHome || path.resolve(home) === path.resolve(state.failHome))) {
        return { status: 2, stdout: '', stderr: 'injected add failure', error: null };
      }
      fs.appendFileSync(config, [
        '[mcp_servers.hard_eng]',
        'command = "node"',
        `args = ["${args.at(-1)}"]`,
        '',
      ].join('\n'));
      return { status: 0, stdout: '', stderr: '', error: null };
    }
    return { status: 2, stdout: '', stderr: 'unsupported fake command', error: null };
  }
  return { calls, run, state };
}

function wiringClient() {
  function inspect(home) {
    const config = path.join(home, '.codex', 'config.toml');
    const text = fs.existsSync(config) ? fs.readFileSync(config, 'utf8') : '';
    const status = text.includes('[plugins."hard-eng@personal"]')
      ? 'MIGRATION_REQUIRED'
      : text.includes('[mcp_servers.hard_eng]')
        ? 'PASS'
        : 'NOT_CONFIGURED';
    return {
      status,
      configured: status !== 'NOT_CONFIGURED',
      owned: status === 'PASS',
      enabled: status !== 'NOT_CONFIGURED',
      evidence_digest: sha256(text),
    };
  }
  function reconcile(home, desired) {
    const observed = inspect(home);
    if ((desired && observed.status === 'PASS') || (!desired && observed.status === 'NOT_CONFIGURED')) {
      return { status: 'PASS', action: 'none', changed: false, evidence_digest: observed.evidence_digest };
    }
    throw new Error('Unexpected wiring reconciliation in cutover fixture.');
  }
  return { inspect, reconcile };
}

function fixture({ failAdd = false } = {}) {
  const codex = fakeCodex({ failAdd });
  return {
    codex,
    wiring: wiringClient(),
    cutover: createCodexCutoverClient({
      run: codex.run,
      env: { PATH: process.env.PATH },
      cronText: '',
      retirementInventory: fixtureRetirementInventory,
    }),
  };
}

test('approved cutover replaces the exact installed owner and rollback restores it byte-for-byte', () => {
  const home = installedHome();
  const beforeConfig = fs.readFileSync(path.join(home, '.codex', 'config.toml'));
  const beforeRetirements = retirementSnapshot(home);
  const beforeZshenv = fs.readFileSync(path.join(home, '.zshenv'));
  const beforeCache = fs.readFileSync(path.join(
    home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng', '1.0.0', 'manifest.json',
  ));
  const beforeE2eCache = fs.readFileSync(path.join(
    home, '.cache', 'hard-eng', 'e2e-playwright', 'package.json',
  ));
  const tools = fixture();
  const dry = runSetup(['migrate', '--home', home, '--live-cutover', '--dry-run'], {
    sourceRoot, now: NOW, wiringClient: tools.wiring, cutoverClient: tools.cutover, cronText: '',
  });
  assert.equal(dry.status, 'DRY_RUN');
  assert.equal(dry.codex_mcp_action, 'cutover');
  assert.equal(dry.codex_mcp.before_status, 'MIGRATION_REQUIRED');
  assert.match(dry.codex_cutover.evidence_digest, /^[a-f0-9]{64}$/);

  const applied = runSetup(['migrate', '--home', home, '--live-cutover', '--confirm', dry.plan_digest], {
    sourceRoot, now: NOW, wiringClient: tools.wiring, cutoverClient: tools.cutover, cronText: '',
  });
  assert.equal(applied.status, 'PASS');
  assert.equal(tools.wiring.inspect(home).status, 'PASS');
  assert.equal(fs.existsSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), false);
  for (const name of Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_skill_links)) {
    assert.throws(() => fs.lstatSync(path.join(home, '.codex', 'skills', name)), /ENOENT/);
  }
  assert.equal(fs.lstatSync(path.join(home, '.codex', 'skills', 'external')).isSymbolicLink(), true);
  assert.equal(fs.realpathSync(path.join(home, '.codex', 'hooks.json')), fs.realpathSync(path.join(home, '.agents', 'hooks', 'hooks.json')));
  assert.throws(() => fs.lstatSync(path.join(home, '.codex', 'mcp-config.json')), /ENOENT/);
  for (const relative of Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_backup_links)) {
    assert.throws(() => fs.lstatSync(path.join(home, relative)), /ENOENT/);
  }
  assert.match(fs.readFileSync(path.join(home, '.zshenv'), 'utf8'), /BEGIN personal toolchain path/);
  assert.doesNotMatch(fs.readFileSync(path.join(home, '.zshenv'), 'utf8'), /hard-eng bootstrap path/);
  assert.equal(fs.existsSync(path.join(home, '.cache', 'hard-eng', 'e2e-playwright')), false);
  assert.match(fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8'), /mcp_servers\.unrelated/);
  for (const name of Object.keys(APPROVED_CUTOVER_INVENTORY.custom_agents)) {
    assert.equal(fs.existsSync(path.join(home, '.codex', 'agents', name)), false);
  }
  assert.equal(fs.existsSync(path.join(home, '.codex', 'skills', 'teach')), false);
  assert.match(applied.rollback_bundle, /^[a-f0-9]{64}$/);

  const rollback = runSetup([
    'rollback', '--home', home, '--backup', applied.rollback_bundle, '--dry-run',
  ], { sourceRoot, now: NOW + 1, wiringClient: tools.wiring, cutoverClient: tools.cutover });
  assert.equal(rollback.previous_codex_mcp_status, 'MIGRATION_REQUIRED');
  const restored = runSetup([
    'rollback', '--home', home, '--backup', applied.rollback_bundle, '--confirm', rollback.plan_digest,
  ], { sourceRoot, now: NOW + 1, wiringClient: tools.wiring, cutoverClient: tools.cutover });
  assert.equal(restored.status, 'PASS');
  assert.equal(tools.wiring.inspect(home).status, 'MIGRATION_REQUIRED');
  for (const name of Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_skill_links)) {
    assert.equal(fs.lstatSync(path.join(home, '.codex', 'skills', name)).isSymbolicLink(), true);
  }
  assert.equal(fs.readlinkSync(path.join(home, '.codex', 'hooks.json')), path.join(home, '.agents', 'codex', 'hooks.json'));
  assert.equal(fs.lstatSync(path.join(home, '.codex', 'mcp-config.json')).isSymbolicLink(), true);
  for (const relative of Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_backup_links)) {
    assert.equal(fs.lstatSync(path.join(home, relative)).isSymbolicLink(), true);
  }
  assert.deepEqual(fs.readFileSync(path.join(home, '.zshenv')), beforeZshenv);
  assert.deepEqual(fs.readFileSync(path.join(
    home, '.cache', 'hard-eng', 'e2e-playwright', 'package.json',
  )), beforeE2eCache);
  assert.deepEqual(fs.readFileSync(path.join(home, '.codex', 'config.toml')), beforeConfig);
  assert.deepEqual(retirementSnapshot(home), beforeRetirements);
  assert.deepEqual(fs.readFileSync(path.join(
    home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng', '1.0.0', 'manifest.json',
  )), beforeCache);
});

test('cutover drift and command failure restore every source and external owner', () => {
  const driftHome = installedHome();
  const driftTools = fixture();
  const dry = runSetup(['migrate', '--home', driftHome, '--live-cutover', '--dry-run'], {
    sourceRoot, now: NOW, wiringClient: driftTools.wiring, cutoverClient: driftTools.cutover, cronText: '',
  });
  fs.appendFileSync(path.join(driftHome, '.codex', 'config.toml'), '# changed\n');
  assert.throws(() => runSetup([
    'migrate', '--home', driftHome, '--live-cutover', '--confirm', dry.plan_digest,
  ], {
    sourceRoot, now: NOW, wiringClient: driftTools.wiring, cutoverClient: driftTools.cutover, cronText: '',
  }), /confirmation digest|changed after approval/i);
  assert.equal(fs.existsSync(path.join(driftHome, '.agents', 'runtime', 'server.mjs')), false);
  assert.equal(driftTools.wiring.inspect(driftHome).status, 'MIGRATION_REQUIRED');

  const failedHome = installedHome();
  const before = fs.readFileSync(path.join(failedHome, '.codex', 'config.toml'));
  const beforeRetirements = retirementSnapshot(failedHome);
  const beforeBootstrap = fs.readFileSync(path.join(failedHome, '.zshenv'));
  const failedTools = fixture();
  const failedDry = runSetup(['migrate', '--home', failedHome, '--live-cutover', '--dry-run'], {
    sourceRoot, now: NOW, wiringClient: failedTools.wiring, cutoverClient: failedTools.cutover, cronText: '',
  });
  failedTools.codex.state.failAdd = true;
  failedTools.codex.state.failHome = failedHome;
  assert.throws(() => runSetup([
    'migrate', '--home', failedHome, '--live-cutover', '--confirm', failedDry.plan_digest,
  ], {
    sourceRoot, now: NOW, wiringClient: failedTools.wiring, cutoverClient: failedTools.cutover, cronText: '',
  }), /standalone MCP add/i);
  assert.deepEqual(fs.readFileSync(path.join(failedHome, '.codex', 'config.toml')), before);
  assert.deepEqual(retirementSnapshot(failedHome), beforeRetirements);
  assert.deepEqual(fs.readFileSync(path.join(failedHome, '.zshenv')), beforeBootstrap);
  assert.equal(fs.existsSync(path.join(failedHome, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), true);
  assert.equal(fs.existsSync(path.join(failedHome, '.cache', 'hard-eng', 'e2e-playwright')), true);
  assert.equal(fs.existsSync(path.join(failedHome, '.agents', 'runtime', 'server.mjs')), false);
});
