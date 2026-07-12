import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { digestValue, sha256 } from '../../runtime/lib/canonical.mjs';
import { createCodexCutoverClient } from '../../runtime/lib/codex-cutover.mjs';
import { APPROVED_CUTOVER_INVENTORY } from '../../runtime/lib/approved-cutover-inventory.mjs';
import { buildSetupPlan } from '../../runtime/lib/setup-transaction.mjs';
import {
  applySetupRecoveryPlan,
  beginSetupTransaction,
  buildSetupRecoveryPlan,
} from '../../runtime/lib/setup-recovery.mjs';
import {
  fixtureRetirementInventory as buildFixtureRetirementInventory,
  seedApprovedLegacyLinks,
} from '../fixtures/cutover-inventory-fixture.mjs';
import { inspectLegacyControlPlane } from '../../runtime/lib/legacy-control-plane.mjs';

function installedHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-'));
  const codex = path.join(home, '.codex');
  const cache = path.join(codex, 'plugins', 'cache', 'personal', 'hard-eng', '1.0.0');
  fs.mkdirSync(cache, { recursive: true });
  fs.chmodSync(path.join(codex, 'plugins', 'cache', 'personal', 'hard-eng'), 0o700);
  fs.chmodSync(cache, 0o700);
  fs.writeFileSync(path.join(cache, 'manifest.json'), '{"name":"hard-eng"}\n');
  fs.writeFileSync(path.join(codex, 'config.toml'), [
    'model = "gpt-test"',
    '[plugins."hard-eng@personal"]',
    'enabled = true',
    '[mcp_servers.codebase-memory-mcp]',
    'command = "/tmp/codebase-memory-mcp"',
    '',
  ].join('\n'), { mode: 0o600 });
  fs.writeFileSync(path.join(codex, 'unrelated.txt'), 'preserve exactly\n');
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

function cutoverClient(options = {}) {
  return createCodexCutoverClient({ cronText: '', ...options, retirementInventory: fixtureRetirementInventory });
}

function fakeCodex({ failAdd = false, volatileOutput = false } = {}) {
  const calls = [];
  function run(args, { home }) {
    calls.push({ args: [...args], home });
    const config = path.join(home, '.codex', 'config.toml');
    if (args.join(' ') === 'plugin remove hard-eng@personal --json') {
      const current = fs.readFileSync(config, 'utf8');
      fs.writeFileSync(config, current.replace('[plugins."hard-eng@personal"]\nenabled = true\n', ''));
      fs.rmSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng'), { recursive: true });
      const suffix = volatileOutput ? `-${calls.length}` : '';
      return { status: 0, stdout: `{"removed":"hard-eng@personal${suffix}"}`, stderr: '', error: null };
    }
    if (args.join(' ') === 'mcp remove codebase-memory-mcp') {
      const current = fs.readFileSync(config, 'utf8');
      fs.writeFileSync(config, current.replace(
        '[mcp_servers.codebase-memory-mcp]\ncommand = "/tmp/codebase-memory-mcp"\n',
        '',
      ));
      return { status: 0, stdout: volatileOutput ? `removed-support-${calls.length}\n` : '', stderr: '', error: null };
    }
    if (args[0] === 'mcp' && args[1] === 'add') {
      if (failAdd) return { status: 2, stdout: '', stderr: 'injected add failure', error: null };
      const target = args.at(-1);
      fs.appendFileSync(config, [
        '[mcp_servers.hard_eng]',
        'command = "node"',
        `args = ["${target}"]`,
        '',
      ].join('\n'));
      return { status: 0, stdout: volatileOutput ? `added-${calls.length}\n` : '', stderr: '', error: null };
    }
    return { status: 2, stdout: '', stderr: 'unsupported fake command', error: null };
  }
  return { calls, run };
}

test('cutover approval binds semantic snapshots instead of volatile command output', () => {
  const home = installedHome();
  const fake = fakeCodex({ volatileOutput: true });
  const client = cutoverClient({ run: fake.run });
  const first = client.preview(home, wiring);
  const second = client.preview(home, wiring);
  assert.equal(first.command_evidence_digest, second.command_evidence_digest);
  assert.equal(first.evidence_digest, second.evidence_digest);
});

function journal() {
  const entries = [];
  return {
    entries,
    prepare(entry) {
      entries.push({ ...entry, status: 'prepared' });
      return entries.length - 1;
    },
    applied(index) {
      entries[index].status = 'applied';
    },
  };
}

const wiring = {
  status: 'MIGRATION_REQUIRED',
  configured: true,
  owned: false,
  enabled: true,
  codebase_memory_mcp_entries: 1,
  codebase_memory_mcp_evidence_digest: 'b'.repeat(64),
  evidence_digest: 'a'.repeat(64),
};
const realCodexAvailable = spawnSync('codex', ['--version'], { encoding: 'utf8' }).status === 0;

function resignCutover(plan, changes) {
  const core = { ...plan, ...changes };
  delete core.evidence_digest;
  return { ...core, evidence_digest: digestValue(core) };
}

test('cutover preview and apply use official Codex commands and preserve unrelated state', () => {
  const home = installedHome();
  const unrelatedBackup = path.join(home, '.codex', 'AGENTS.md.backup.20260101010101');
  fs.writeFileSync(unrelatedBackup, 'preserve unrelated regular backup\n');
  const unrelatedBackupBefore = fs.readFileSync(unrelatedBackup);
  const fake = fakeCodex();
  const client = cutoverClient({ run: fake.run, env: { PATH: process.env.PATH } });
  const plan = client.preview(home, wiring);
  assert.equal(plan.schema, 'hard-eng/codex-cutover/v2');
  assert.equal(plan.before.config.type, 'file');
  assert.equal(plan.before.cache.type, 'directory');
  assert.equal(plan.removed.cache, null);
  assert.equal(plan.support_retired.cache, null);
  assert.equal(plan.after.cache, null);
  assert.equal(plan.skill_links.length, 46);
  assert.deepEqual(
    plan.skill_links.map((entry) => entry.path),
    Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_skill_links)
      .sort()
      .map((name) => `.codex/skills/${name}`),
  );
  assert.deepEqual(plan.replace_links.map((entry) => entry.path), ['.codex/hooks.json']);
  assert.deepEqual(plan.remove_links.map((entry) => entry.path).sort(), [
    ...Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_backup_links),
    '.codex/mcp-config.json',
  ].sort());
  assert.equal(plan.bootstrap_path.path, '.zshenv');
  assert.equal(plan.bootstrap_path.before.type, 'file');
  assert.equal(plan.bootstrap_path.after.type, 'file');
  assert.equal(plan.e2e_cache.path, '.cache/hard-eng/e2e-playwright');
  assert.equal(plan.e2e_cache.before.type, 'directory');
  assert.equal(plan.custom_agents.length, 25);
  assert.equal(plan.duplicate_teach.path, '.codex/skills/teach');
  assert.match(plan.retirement_inventory_digest, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(plan).includes(home), false);
  assert.match(plan.evidence_digest, /^[a-f0-9]{64}$/);

  const transaction = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-transaction-'));
  const context = journal();
  const applied = client.apply(home, plan, { transaction, transactionContext: context });
  assert.equal(applied.status, 'PASS');
  assert.equal(applied.action, 'replace');
  assert.equal(applied.applied.length, 2);
  assert.equal(context.entries.length, 4);
  assert.equal(context.entries.every((entry) => entry.status === 'applied'), true);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), false);
  assert.equal(fs.readFileSync(path.join(home, '.codex', 'unrelated.txt'), 'utf8'), 'preserve exactly\n');
  assert.deepEqual(fs.readFileSync(unrelatedBackup), unrelatedBackupBefore);
  assert.match(fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8'), /mcp_servers\.hard_eng/);
  assert.doesNotMatch(fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8'), /codebase-memory-mcp/);
  assert.deepEqual(fake.calls.slice(-3).map((call) => call.args.slice(0, 3)), [
    ['plugin', 'remove', 'hard-eng@personal'],
    ['mcp', 'remove', 'codebase-memory-mcp'],
    ['mcp', 'add', 'hard_eng'],
  ]);
});

test('cutover refuses drift before running a live command', () => {
  const home = installedHome();
  const fake = fakeCodex();
  const client = cutoverClient({ run: fake.run });
  const plan = client.preview(home, wiring);
  fs.appendFileSync(path.join(home, '.codex', 'config.toml'), '# drift\n');
  const before = fake.calls.length;
  const transaction = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-transaction-'));
  assert.throws(
    () => client.apply(home, plan, { transaction, transactionContext: journal() }),
    /changed after approval/i,
  );
  assert.equal(fake.calls.length, before);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), true);
});

test('cutover refuses a symlinked legacy skill directory before inventory or commands', () => {
  const home = installedHome();
  const inventory = fixtureRetirementInventory(home);
  const skills = path.join(home, '.codex', 'skills');
  fs.rmSync(skills, { recursive: true });
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-external-skills-'));
  fs.symlinkSync(outside, skills);
  const fake = fakeCodex();
  const client = createCodexCutoverClient({
    cronText: '', run: fake.run, retirementInventory: inventory,
  });

  assert.throws(() => client.preview(home, wiring), /skill-link directory is unsafe/i);
  assert.equal(fake.calls.length, 0);
});

test('cutover blocks unresolved native control planes and revalidates immediately before mutation', () => {
  const blockedHome = installedHome();
  fs.mkdirSync(path.join(blockedHome, '.codex', 'bin'), { recursive: true });
  fs.writeFileSync(path.join(blockedHome, '.codex', 'bin', 'codex-watchdog'), [
    '#!/bin/sh', '# Managed by hard-eng installer.', '',
  ].join('\n'));
  const blockedFake = fakeCodex();
  assert.throws(
    () => cutoverClient({ run: blockedFake.run }).preview(blockedHome, wiring),
    /control-plane retirement is unresolved/i,
  );
  assert.equal(blockedFake.calls.length, 0);

  const driftHome = installedHome();
  const driftFake = fakeCodex();
  let cron = '';
  const client = createCodexCutoverClient({
    run: driftFake.run,
    retirementInventory: fixtureRetirementInventory,
    controlPlaneInspector(home) {
      return inspectLegacyControlPlane(home, { cronText: cron });
    },
  });
  const plan = client.preview(driftHome, wiring);
  const before = driftFake.calls.length;
  cron = '*/5 * * * * "$HOME/.codex/bin/codex-watchdog"';
  const transaction = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-control-plane-'));
  assert.throws(
    () => client.apply(driftHome, plan, { transaction, transactionContext: journal() }),
    /control-plane retirement is unresolved/i,
  );
  assert.equal(driftFake.calls.length, before);
});

test('cutover plan is bound to the selected home and exact wiring observation', () => {
  const home = installedHome();
  const fake = fakeCodex();
  const client = cutoverClient({ run: fake.run });
  assert.throws(() => client.preview(home, { ...wiring, status: 'PASS' }), /installed-cache owner/i);
  assert.throws(() => client.preview(home, {
    ...wiring,
    codebase_memory_mcp_entries: 0,
  }), /exact approved Codebase Memory MCP registration/i);
  assert.equal(fake.calls.length, 0);
  const plan = client.preview(home, wiring);
  assert.notEqual(plan.target_home_digest, sha256('/another/home'));
  const transaction = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-transaction-'));
  assert.throws(
    () => client.apply('/another/home', plan, { transaction, transactionContext: journal() }),
    /selected home/i,
  );
});

test('cutover refuses malformed bootstrap ownership and unknown E2E cache entries', () => {
  const malformed = installedHome();
  fs.writeFileSync(path.join(malformed, '.zshenv'), '# BEGIN hard-eng bootstrap path\n');
  assert.throws(
    () => cutoverClient({ run: fakeCodex().run }).preview(malformed, wiring),
    /bootstrap.*marker|marker.*bootstrap/i,
  );

  const unknownCache = installedHome();
  fs.writeFileSync(path.join(unknownCache, '.cache', 'hard-eng', 'e2e-playwright', 'unknown.txt'), 'preserve\n');
  assert.throws(
    () => cutoverClient({ run: fakeCodex().run }).preview(unknownCache, wiring),
    /cache.*(?:unknown|unexpected)/i,
  );
});

test('cutover refuses custom-agent and duplicate-Teach drift before official commands run', () => {
  const changedAgentHome = installedHome();
  const changedAgentFake = fakeCodex();
  const changedAgentInventory = fixtureRetirementInventory(changedAgentHome);
  fs.appendFileSync(path.join(changedAgentHome, '.codex', 'agents', 'worker.toml'), '# changed\n');
  assert.throws(
    () => createCodexCutoverClient({
      run: changedAgentFake.run,
      cronText: '',
      retirementInventory: changedAgentInventory,
    }).preview(changedAgentHome, wiring),
    /custom-agent profile changed after approval/i,
  );
  assert.equal(changedAgentFake.calls.length, 0);

  const extraAgentHome = installedHome();
  const extraAgentFake = fakeCodex();
  const extraAgentInventory = fixtureRetirementInventory(extraAgentHome);
  fs.writeFileSync(path.join(extraAgentHome, '.codex', 'agents', 'unapproved.toml'), 'name = "unapproved"\n');
  assert.throws(
    () => createCodexCutoverClient({
      run: extraAgentFake.run,
      cronText: '',
      retirementInventory: extraAgentInventory,
    }).preview(extraAgentHome, wiring),
    /custom-agent inventory changed after approval/i,
  );
  assert.equal(extraAgentFake.calls.length, 0);

  const missingAgentHome = installedHome();
  const missingAgentFake = fakeCodex();
  const missingAgentInventory = fixtureRetirementInventory(missingAgentHome);
  fs.unlinkSync(path.join(missingAgentHome, '.codex', 'agents', 'worker.toml'));
  assert.throws(
    () => createCodexCutoverClient({
      run: missingAgentFake.run,
      cronText: '',
      retirementInventory: missingAgentInventory,
    }).preview(missingAgentHome, wiring),
    /custom-agent inventory changed after approval/i,
  );
  assert.equal(missingAgentFake.calls.length, 0);

  const changedTeachHome = installedHome();
  const changedTeachFake = fakeCodex();
  const changedTeachInventory = fixtureRetirementInventory(changedTeachHome);
  fs.appendFileSync(path.join(changedTeachHome, '.codex', 'skills', 'teach', 'SKILL.md'), '# changed\n');
  assert.throws(
    () => createCodexCutoverClient({
      run: changedTeachFake.run,
      cronText: '',
      retirementInventory: changedTeachInventory,
    }).preview(changedTeachHome, wiring),
    /duplicate Teach owner changed after approval/i,
  );
  assert.equal(changedTeachFake.calls.length, 0);

  const missingTeachHome = installedHome();
  const missingTeachFake = fakeCodex();
  const missingTeachInventory = fixtureRetirementInventory(missingTeachHome);
  fs.rmSync(path.join(missingTeachHome, '.codex', 'skills', 'teach'), { recursive: true });
  assert.throws(
    () => createCodexCutoverClient({
      run: missingTeachFake.run,
      cronText: '',
      retirementInventory: missingTeachInventory,
    }).preview(missingTeachHome, wiring),
    /duplicate Teach directory is missing/i,
  );
  assert.equal(missingTeachFake.calls.length, 0);
});

test('cutover fails closed on missing, drifted, or extra legacy links before official commands run', () => {
  const expectBlocked = (mutate, pattern) => {
    const home = installedHome();
    const inventory = fixtureRetirementInventory(home);
    const fake = fakeCodex();
    mutate(home);
    assert.throws(
      () => createCodexCutoverClient({
        run: fake.run,
        cronText: '',
        retirementInventory: inventory,
      }).preview(home, wiring),
      pattern,
    );
    assert.equal(fake.calls.length, 0);
  };

  expectBlocked((home) => {
    fs.unlinkSync(path.join(home, '.codex', 'skills', 'appwrite-backend'));
  }, /legacy skill link changed after approval/i);
  expectBlocked((home) => {
    const target = path.join(home, '.codex', 'skills', 'appwrite-backend');
    fs.unlinkSync(target);
    fs.symlinkSync(path.join(home, '.agents', 'skills', 'changed'), target);
  }, /legacy skill link changed after approval/i);
  expectBlocked((home) => {
    fs.symlinkSync(
      path.join(home, '.agents', 'skills', 'unapproved'),
      path.join(home, '.codex', 'skills', 'unapproved'),
    );
  }, /unapproved legacy skill link/i);

  const firstBackup = Object.keys(APPROVED_CUTOVER_INVENTORY.legacy_backup_links)[0];
  expectBlocked((home) => {
    fs.unlinkSync(path.join(home, firstBackup));
  }, /backup-link inventory changed after approval/i);
  expectBlocked((home) => {
    const target = path.join(home, firstBackup);
    fs.unlinkSync(target);
    fs.symlinkSync('/private/tmp/hard-eng-drift/AGENTS.md', target);
  }, /legacy backup link changed after approval/i);
  expectBlocked((home) => {
    fs.symlinkSync(
      path.join(home, '.agents', 'AGENTS.md'),
      path.join(home, '.codex', 'AGENTS.md.backup.20990101000000'),
    );
  }, /backup-link inventory changed after approval/i);
});

test('setup accepts only exact, non-overlapping cutover link categories', () => {
  const home = installedHome();
  const client = cutoverClient({ run: fakeCodex().run });
  const cutover = client.preview(home, wiring);
  const build = (candidate) => buildSetupPlan({
    mode: 'migrate',
    home,
    sourceRoot: path.resolve('.'),
    codexMcp: wiring,
    codexCutover: candidate,
    liveCutover: true,
  });

  const duplicate = resignCutover(cutover, {
    remove_links: [...cutover.remove_links, cutover.skill_links[0]],
  });
  assert.throws(() => build(duplicate), /invalid entry/i);

  const forgedReplacement = resignCutover(cutover, {
    replace_links: [{ ...cutover.replace_links[0], path: '.codex/AGENTS.md' }],
  });
  assert.throws(() => build(forgedReplacement), /invalid entry/i);

  const forgedBootstrap = resignCutover(cutover, {
    bootstrap_path: { ...cutover.bootstrap_path, path: '.profile' },
  });
  assert.throws(() => build(forgedBootstrap), /bootstrap ledger/i);

  const forgedCache = resignCutover(cutover, {
    e2e_cache: { ...cutover.e2e_cache, path: '.cache/unrelated' },
  });
  assert.throws(() => build(forgedCache), /E2E-cache ledger/i);

  const forgedAgent = resignCutover(cutover, {
    custom_agents: cutover.custom_agents.map((entry, index) => index === 0
      ? { ...entry, before: { ...entry.before, hash: 'f'.repeat(64) } }
      : entry),
  });
  assert.throws(() => build(forgedAgent), /custom-agent profile changed after cutover approval/i);

  const forgedAgentParity = resignCutover(cutover, {
    custom_agents: cutover.custom_agents.map((entry, index) => index === 0
      ? { ...entry, parity: { ...entry.parity, required_terms: ['term-not-present-in-any-owner'] } }
      : entry),
  });
  assert.throws(() => build(forgedAgentParity), /parity obligation is unproven/i);

  const forgedTeach = resignCutover(cutover, {
    duplicate_teach: {
      ...cutover.duplicate_teach,
      before: { ...cutover.duplicate_teach.before, hash: 'f'.repeat(64) },
    },
  });
  assert.throws(() => build(forgedTeach), /duplicate Teach owner changed after cutover approval/i);

  const forgedRetirementDigest = resignCutover(cutover, {
    retirement_inventory_digest: 'f'.repeat(64),
  });
  assert.throws(() => build(forgedRetirementDigest), /retirement inventory digest is invalid/i);

  fs.unlinkSync(path.join(home, '.codex', 'hooks.json'));
  fs.symlinkSync('/opt/external/hooks.json', path.join(home, '.codex', 'hooks.json'));
  assert.throws(() => build(cutover), /changed after approval/i);
});

test('cutover journal recovery unwinds the three config transitions in reverse', () => {
  const home = installedHome();
  const beforeConfig = fs.readFileSync(path.join(home, '.codex', 'config.toml'));
  const fake = fakeCodex();
  const client = cutoverClient({ run: fake.run });
  const cutover = client.preview(home, wiring);
  const setupPlan = {
    plan_digest: 'b'.repeat(64),
    target_home_digest: sha256(path.resolve(home)),
  };
  const context = beginSetupTransaction({
    home,
    plan: setupPlan,
    previousManifest: null,
    previousCodexMcpStatus: 'MIGRATION_REQUIRED',
  });
  client.apply(home, cutover, { transaction: context.directory, transactionContext: context });

  const isProcessAlive = () => false;
  const recovery = buildSetupRecoveryPlan({ home, isProcessAlive });
  assert.equal(recovery.operations.filter((entry) => entry.path === '.codex/config.toml').length, 3);
  const wiringClient = {
    inspect() {
      const text = fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8');
      return { status: text.includes('[plugins."hard-eng@personal"]') ? 'MIGRATION_REQUIRED' : 'PASS', evidence_digest: sha256(text) };
    },
    reconcile() {
      throw new Error('Recovery must restore the exact installed owner from its journal.');
    },
  };
  const restored = applySetupRecoveryPlan(recovery, { home, wiringClient, isProcessAlive });
  assert.equal(restored.status, 'PASS');
  assert.deepEqual(fs.readFileSync(path.join(home, '.codex', 'config.toml')), beforeConfig);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), true);
});

test('real Codex CLI removes the isolated plugin and Codebase Memory MCP owners, then adds standalone wiring', {
  skip: realCodexAvailable ? false : 'Codex CLI is unavailable in this test environment.',
}, () => {
  const home = installedHome();
  const client = cutoverClient();
  const plan = client.preview(home, wiring);
  const transaction = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-cutover-real-'));
  const result = client.apply(home, plan, { transaction, transactionContext: journal() });
  assert.equal(result.status, 'PASS');
  const env = { ...process.env, HOME: home };
  delete env.CODEX_HOME;
  const observed = spawnSync('codex', ['mcp', 'get', 'hard_eng', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(observed.status, 0, observed.stderr);
  const entry = JSON.parse(observed.stdout);
  assert.deepEqual(entry.transport.args, [path.join(home, '.agents', 'runtime', 'server.mjs')]);
  const retired = spawnSync('codex', ['mcp', 'get', 'codebase-memory-mcp', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.notEqual(retired.status, 0);
  assert.equal(fs.existsSync(path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng')), false);
});
