import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';
import {
  atomicWrite,
  inspectSetupTarget,
  mkdirPrivate,
  safeSetupTarget,
} from './setup-transaction.mjs';
import { redactErrorMessage } from './redact.mjs';
import { copyDirectoryExact } from './fs-exact.mjs';
import { APPROVED_CUTOVER_INVENTORY } from './approved-cutover-inventory.mjs';
import {
  BOOTSTRAP_PATH,
  E2E_CACHE_PATH,
  neutralizeBootstrap,
  validateE2eCache,
} from './live-cutover-owned.mjs';
import {
  assertLegacyControlPlaneReady,
  inspectLegacyControlPlane,
} from './legacy-control-plane.mjs';

const SCHEMA = 'hard-eng/codex-cutover/v1';
const CONFIG_PATH = '.codex/config.toml';
const CACHE_PATH = '.codex/plugins/cache/personal/hard-eng';

function childEnvironment(home, env) {
  const output = { HOME: path.resolve(home), NO_COLOR: '1' };
  for (const key of [
    'PATH', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM',
  ]) {
    if (env[key] !== undefined) output[key] = env[key];
  }
  return output;
}

function defaultRun(args, { home, env }) {
  const result = spawnSync('codex', args, {
    env: childEnvironment(home, env),
    encoding: 'utf8',
    timeout: 30_000,
    maxBuffer: 512 * 1024,
    shell: false,
  });
  return {
    status: result.status,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? '',
    error: result.error ?? null,
  };
}

function runChecked(run, args, options, label) {
  const result = run(args, options);
  const evidenceDigest = sha256(`${result.stdout ?? ''}\0${result.stderr ?? ''}`);
  if (result.error || result.status !== 0) {
    const detail = redactErrorMessage(result.error?.message ?? result.stderr ?? result.stdout ?? 'unknown failure');
    throw new Error(`${label} failed (${evidenceDigest.slice(0, 12)}): ${detail}`);
  }
  return evidenceDigest;
}

function snapshot(value) {
  if (!value) return null;
  return {
    type: value.type,
    hash: value.hash,
    mode: value.mode ?? null,
    ...(value.link_target !== undefined ? { link_target: value.link_target } : {}),
  };
}

function observe(home, relative) {
  return snapshot(inspectSetupTarget(safeSetupTarget(home, relative)));
}

function same(actual, expected) {
  if (!actual || !expected) return actual === expected;
  return actual.type === expected.type
    && actual.hash === expected.hash
    && (actual.mode ?? null) === (expected.mode ?? null)
    && (actual.link_target ?? null) === (expected.link_target ?? null);
}

function assertInitialState(home) {
  const config = observe(home, CONFIG_PATH);
  const cache = observe(home, CACHE_PATH);
  if (config?.type !== 'file') throw new Error('Codex cutover requires one regular config.toml owner.');
  if (cache?.type !== 'directory') throw new Error('Codex cutover requires the exact installed Hard Eng cache owner.');
  return { config, cache };
}

function copyTarget(source, destination, value, label = 'Codex cutover') {
  fs.mkdirSync(path.dirname(destination), { recursive: true, mode: 0o700 });
  if (value.type === 'file') {
    fs.copyFileSync(source, destination);
    fs.chmodSync(destination, value.mode);
  } else if (value.type === 'directory') {
    copyDirectoryExact(source, destination);
  } else {
    throw new Error('Codex cutover snapshots must be regular files or directories.');
  }
  if (!same(snapshot(inspectSetupTarget(destination)), value)) {
    throw new Error(`${label} snapshot verification failed.`);
  }
}

function removeTarget(target) {
  const current = inspectSetupTarget(target);
  if (!current) return;
  if (current.type === 'directory') fs.rmSync(target, { recursive: true });
  else fs.unlinkSync(target);
}

function restoreTarget(target, backup, value) {
  removeTarget(target);
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o755 });
  if (value.type === 'file') {
    atomicWrite(target, fs.readFileSync(backup), value.mode);
  } else {
    copyDirectoryExact(backup, target);
  }
  if (!same(snapshot(inspectSetupTarget(target)), value)) {
    throw new Error('Codex cutover restore verification failed.');
  }
}

function commandPlan(actualHome) {
  return {
    remove: ['plugin', 'remove', 'hard-eng@personal', '--json'],
    add: [
      'mcp', 'add', 'hard_eng', '--', 'node',
      path.join(path.resolve(actualHome), '.agents', 'runtime', 'server.mjs'),
    ],
  };
}

function approvedSkillLinkEntries(inventory) {
  const entries = Object.entries(inventory?.legacy_skill_links ?? {})
    .sort(([left], [right]) => left.localeCompare(right));
  if (entries.length !== 46) {
    throw new Error('Approved legacy skill-link inventory must contain exactly 46 links.');
  }
  for (const [name, hash] of entries) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name) || !/^[a-f0-9]{64}$/.test(hash)) {
      throw new Error('Approved legacy skill-link inventory contains an invalid entry.');
    }
  }
  return entries;
}

function approvedBackupLinkEntries(inventory) {
  const entries = Object.entries(inventory?.legacy_backup_links ?? {})
    .sort(([left], [right]) => left.localeCompare(right));
  if (entries.length !== 9) {
    throw new Error('Approved legacy backup-link inventory must contain exactly nine links.');
  }
  for (const [relative, hash] of entries) {
    if (
      !/^\.codex\/(?:AGENTS\.md|hooks\.json)\.backup\.\d{8,}$/.test(relative)
      || !/^[a-f0-9]{64}$/.test(hash)
    ) throw new Error('Approved legacy backup-link inventory contains an invalid entry.');
  }
  return entries;
}

function approvedSymlink(home, relative, expectedHash, label) {
  const before = observe(home, relative);
  if (!before || before.type !== 'symlink' || before.hash !== expectedHash) {
    throw new Error(`${label} changed after approval: ${relative}.`);
  }
  return { path: relative, before: { type: before.type, hash: before.hash, mode: null } };
}

function requiredRealDirectory(home, relative, label) {
  const directory = safeSetupTarget(home, relative);
  const stat = fs.lstatSync(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`${label} is unsafe.`);
  return directory;
}

function ownedSkillLinks(home, inventory) {
  const directory = requiredRealDirectory(home, '.codex/skills', 'Approved legacy skill-link directory');
  const expected = approvedSkillLinkEntries(inventory);
  const root = path.join(path.resolve(home), '.agents', 'skills');
  const expectedNames = new Set(expected.map(([name]) => name));
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isSymbolicLink()) continue;
    const target = path.join(directory, entry.name);
    const resolved = path.resolve(path.dirname(target), fs.readlinkSync(target));
    const relativeTarget = path.relative(root, resolved);
    if (!relativeTarget || relativeTarget.startsWith('..') || path.isAbsolute(relativeTarget)) continue;
    if (!expectedNames.has(entry.name)) {
      throw new Error(`Unapproved legacy skill link blocks cutover: .codex/skills/${entry.name}.`);
    }
  }
  return expected.map(([name, hash]) => approvedSymlink(
    home,
    `.codex/skills/${name}`,
    hash,
    'Legacy skill link',
  ));
}

function resolvedLink(target) {
  const stat = fs.lstatSync(target);
  if (!stat.isSymbolicLink()) return null;
  return path.resolve(path.dirname(target), fs.readlinkSync(target));
}

function hardEngTemporaryTarget(target, suffix) {
  const normalized = path.resolve(target);
  const roots = ['/private/tmp', '/tmp', os.tmpdir()].map((entry) => path.resolve(entry));
  return roots.some((root) => {
    const relative = path.relative(root, normalized);
    return relative
      && !relative.startsWith('..')
      && !path.isAbsolute(relative)
      && relative.split(path.sep)[0].startsWith('hard-eng-');
  }) && normalized.endsWith(suffix);
}

function globalLinkLedger(home, inventory) {
  const codex = requiredRealDirectory(home, '.codex', 'Approved Codex cutover root');
  const replace = [];
  const remove = [];
  const record = (relative, list) => {
    const before = observe(home, relative);
    list.push({ path: relative, before: { type: before.type, hash: before.hash, mode: null } });
  };

  const hooksRelative = '.codex/hooks.json';
  const hooks = safeSetupTarget(home, hooksRelative);
  try {
    if (resolvedLink(hooks) === path.join(path.resolve(home), '.agents', 'codex', 'hooks.json')) {
      record(hooksRelative, replace);
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  const mcpRelative = '.codex/mcp-config.json';
  const mcp = safeSetupTarget(home, mcpRelative);
  try {
    const target = resolvedLink(mcp);
    if (target && !fs.existsSync(target) && hardEngTemporaryTarget(target, `${path.sep}mcp-config.json`)) {
      record(mcpRelative, remove);
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  const approvedBackups = approvedBackupLinkEntries(inventory);
  const expectedPaths = approvedBackups.map(([relative]) => relative);
  const observedPaths = fs.readdirSync(codex, { withFileTypes: true })
    .filter((entry) => entry.isSymbolicLink()
      && /^(?:AGENTS\.md|hooks\.json)\.backup\.\d{8,}$/.test(entry.name))
    .map((entry) => `.codex/${entry.name}`)
    .sort();
  if (JSON.stringify(observedPaths) !== JSON.stringify(expectedPaths)) {
    throw new Error('Legacy backup-link inventory changed after approval.');
  }
  remove.push(...approvedBackups.map(([relative, hash]) => approvedSymlink(
    home,
    relative,
    hash,
    'Legacy backup link',
  )));
  return { replace_links: replace, remove_links: remove };
}

function bootstrapPathPlan(home) {
  const target = safeSetupTarget(home, BOOTSTRAP_PATH);
  const before = inspectSetupTarget(target);
  if (!before) return null;
  if (before.type !== 'file') throw new Error('Hard Eng bootstrap owner must be a regular file.');
  const afterBytes = neutralizeBootstrap(fs.readFileSync(target));
  if (!afterBytes) return null;
  return {
    path: BOOTSTRAP_PATH,
    before: snapshot(before),
    after: { type: 'file', hash: sha256(afterBytes), mode: before.mode },
  };
}

function e2eCachePlan(home) {
  const target = safeSetupTarget(home, E2E_CACHE_PATH);
  const before = inspectSetupTarget(target);
  if (!before) return null;
  if (before.type !== 'directory') throw new Error('Hard Eng E2E cache owner must be a directory.');
  validateE2eCache(target);
  return { path: E2E_CACHE_PATH, before: snapshot(before) };
}

function retirementPlan(home, inventory) {
  if (inventory?.schema !== 'hard-eng/approved-cutover-inventory/v1') {
    throw new Error('Approved cutover retirement inventory is invalid.');
  }
  const expectedAgents = Object.keys(inventory.custom_agents ?? {}).sort();
  if (expectedAgents.length !== 25) throw new Error('Approved custom-agent retirement inventory must contain exactly 25 profiles.');
  const agentsRoot = safeSetupTarget(home, '.codex/agents');
  const agentsRootState = inspectSetupTarget(agentsRoot);
  if (!agentsRootState || agentsRootState.type !== 'directory') {
    throw new Error('Approved custom-agent directory is missing or unsafe.');
  }
  const actualAgents = fs.readdirSync(agentsRoot, { withFileTypes: true })
    .map((entry) => {
      if (!entry.isFile() || entry.isSymbolicLink()) throw new Error('Custom-agent inventory contains a non-file entry.');
      return entry.name;
    })
    .sort();
  if (JSON.stringify(actualAgents) !== JSON.stringify(expectedAgents)) {
    throw new Error('Custom-agent inventory changed after approval.');
  }
  const customAgents = expectedAgents.map((name) => {
    const expected = inventory.custom_agents[name];
    if (!/^[A-Za-z0-9-]+\.toml$/.test(name) || !/^[a-f0-9]{64}$/.test(expected?.hash ?? '')) {
      throw new Error('Approved custom-agent entry is invalid.');
    }
    const expectedProofId = `custom-agent/${name.slice(0, -'.toml'.length)}`;
    if (
      expected.proof_id !== expectedProofId
      || !Array.isArray(expected.owners)
      || expected.owners.length < 1
      || expected.owners.some((owner) => (
        typeof owner !== 'string'
        || path.isAbsolute(owner)
        || owner.split('/').includes('..')
        || !owner.endsWith('.md')
      ))
      || new Set(expected.owners).size !== expected.owners.length
      || !Array.isArray(expected.required_terms)
      || expected.required_terms.length < 1
      || expected.required_terms.some((term) => (
        typeof term !== 'string' || !term.trim() || term.length > 80 || /[\r\n\0]/.test(term)
      ))
    ) throw new Error(`Approved custom-agent parity proof is invalid: ${name}.`);
    const relative = `.codex/agents/${name}`;
    const before = observe(home, relative);
    if (!before || before.type !== 'file' || before.hash !== expected.hash) {
      throw new Error(`Custom-agent profile changed after approval: ${name}.`);
    }
    return {
      path: relative,
      before,
      parity: {
        proof_id: expected.proof_id,
        owners: [...expected.owners],
        required_terms: [...expected.required_terms],
      },
    };
  });

  const teach = inventory.duplicate_teach;
  if (
    teach?.path !== '.codex/skills/teach'
    || !/^[a-f0-9]{64}$/.test(teach.hash ?? '')
    || !Array.isArray(teach.files)
  ) throw new Error('Approved duplicate Teach inventory is invalid.');
  const teachRoot = safeSetupTarget(home, teach.path);
  const teachRootState = inspectSetupTarget(teachRoot);
  if (!teachRootState || teachRootState.type !== 'directory') {
    throw new Error('Approved duplicate Teach directory is missing or unsafe.');
  }
  const actualTeachFiles = fs.readdirSync(teachRoot, { withFileTypes: true })
    .map((entry) => {
      if (!entry.isFile() || entry.isSymbolicLink()) throw new Error('Duplicate Teach inventory contains a non-file entry.');
      return entry.name;
    })
    .sort();
  if (JSON.stringify(actualTeachFiles) !== JSON.stringify([...teach.files].sort())) {
    throw new Error('Duplicate Teach inventory changed after approval.');
  }
  const teachBefore = snapshot(teachRootState);
  if (teachBefore.hash !== teach.hash) {
    throw new Error('Duplicate Teach owner changed after approval.');
  }
  const digestInput = {
    legacy_skill_links: Object.fromEntries(approvedSkillLinkEntries(inventory)),
    legacy_backup_links: Object.fromEntries(approvedBackupLinkEntries(inventory)),
    duplicate_teach: { path: teach.path, hash: teach.hash, files: [...teach.files].sort() },
    custom_agents: Object.fromEntries(expectedAgents.map((name) => {
      const entry = inventory.custom_agents[name];
      return [name, {
        hash: entry.hash,
        proof_id: entry.proof_id,
        owners: [...entry.owners],
        required_terms: [...entry.required_terms],
      }];
    })),
  };
  return {
    custom_agents: customAgents,
    duplicate_teach: { path: teach.path, before: teachBefore, files: [...teach.files].sort() },
    retirement_inventory_digest: digestValue(digestInput),
  };
}

function executePreview(run, env, actualHome, shadowHome) {
  const commands = commandPlan(actualHome);
  const removalDigest = runChecked(
    run,
    commands.remove,
    { home: shadowHome, env },
    'Codex Hard Eng plugin removal preview',
  );
  const removed = {
    config: observe(shadowHome, CONFIG_PATH),
    cache: observe(shadowHome, CACHE_PATH),
  };
  if (removed.config?.type !== 'file' || removed.cache !== null) {
    throw new Error('Codex removal preview did not remove only the exact installed cache owner.');
  }
  const addDigest = runChecked(
    run,
    commands.add,
    { home: shadowHome, env },
    'Codex standalone MCP add preview',
  );
  const after = {
    config: observe(shadowHome, CONFIG_PATH),
    cache: observe(shadowHome, CACHE_PATH),
  };
  if (after.config?.type !== 'file' || after.cache !== null) {
    throw new Error('Codex cutover preview did not reach the standalone configuration.');
  }
  return {
    removed,
    after,
    evidenceDigest: sha256(`${removalDigest}\0${addDigest}`),
  };
}

function collapsedApplied(home, transaction, before) {
  return [
    {
      target: safeSetupTarget(home, CONFIG_PATH),
      backup: path.join(transaction, 'cutover-config.before'),
      existed: true,
      type: 'file',
      link_target: null,
      before: before.config,
      operation: { path: CONFIG_PATH, action: 'write', rollback_action: 'restore-current' },
    },
    {
      target: safeSetupTarget(home, CACHE_PATH),
      backup: path.join(transaction, 'cutover-cache.before'),
      existed: true,
      type: 'directory',
      link_target: null,
      before: before.cache,
      operation: { path: CACHE_PATH, action: 'remove', rollback_action: 'restore-current' },
    },
  ];
}

export function createCodexCutoverClient({
  env = process.env,
  run = defaultRun,
  retirementInventory = APPROVED_CUTOVER_INVENTORY,
  cronText = undefined,
  controlPlaneInspector = inspectLegacyControlPlane,
} = {}) {
  function preview(home, wiring) {
    if (wiring?.status !== 'MIGRATION_REQUIRED') {
      throw new Error('Codex cutover requires the exact installed-cache owner.');
    }
    if (!/^[a-f0-9]{64}$/.test(wiring.evidence_digest ?? '')) {
      throw new Error('Codex cutover requires a valid wiring observation.');
    }
    const before = assertInitialState(home);
    const legacyControlPlane = controlPlaneInspector(home, { env, cronText });
    assertLegacyControlPlaneReady(legacyControlPlane);
    const shadow = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-codex-cutover-'));
    try {
      const inventory = typeof retirementInventory === 'function'
        ? retirementInventory(home)
        : retirementInventory;
      const skillLinks = ownedSkillLinks(home, inventory);
      const globalLinks = globalLinkLedger(home, inventory);
      const bootstrapPath = bootstrapPathPlan(home);
      const e2eCache = e2eCachePlan(home);
      const approvedRetirements = retirementPlan(home, inventory);
      mkdirPrivate(path.join(shadow, '.codex'));
      copyTarget(
        safeSetupTarget(home, CONFIG_PATH),
        safeSetupTarget(shadow, CONFIG_PATH),
        before.config,
        'Codex config',
      );
      copyTarget(
        safeSetupTarget(home, CACHE_PATH),
        safeSetupTarget(shadow, CACHE_PATH),
        before.cache,
        'Installed Hard Eng cache',
      );
      const observed = executePreview(run, env, home, shadow);
      const core = {
        schema: SCHEMA,
        target_home_digest: sha256(path.resolve(home)),
        wiring_evidence_digest: wiring.evidence_digest,
        before,
        removed: observed.removed,
        after: observed.after,
        skill_links: skillLinks,
        replace_links: globalLinks.replace_links,
        remove_links: globalLinks.remove_links,
        bootstrap_path: bootstrapPath,
        e2e_cache: e2eCache,
        custom_agents: approvedRetirements.custom_agents,
        duplicate_teach: approvedRetirements.duplicate_teach,
        retirement_inventory_digest: approvedRetirements.retirement_inventory_digest,
        command_evidence_digest: observed.evidenceDigest,
        legacy_control_plane: legacyControlPlane,
      };
      return { ...core, evidence_digest: digestValue(core) };
    } finally {
      fs.rmSync(shadow, { recursive: true, force: true });
    }
  }

  function apply(home, plan, { transaction, transactionContext }) {
    if (plan?.schema !== SCHEMA) throw new Error('Codex cutover plan schema is invalid.');
    if (sha256(path.resolve(home)) !== plan.target_home_digest) {
      throw new Error('Codex cutover plan belongs to another selected home.');
    }
    if (!transaction || !transactionContext) throw new Error('Codex cutover requires a durable transaction.');
    const legacyControlPlane = controlPlaneInspector(home, { env, cronText });
    assertLegacyControlPlaneReady(legacyControlPlane);
    if (legacyControlPlane.evidence_digest !== plan.legacy_control_plane?.evidence_digest) {
      throw new Error('Legacy control-plane state changed after cutover approval.');
    }
    const current = assertInitialState(home);
    if (!same(current.config, plan.before?.config) || !same(current.cache, plan.before?.cache)) {
      throw new Error('Codex cutover target changed after approval.');
    }
    const configTarget = safeSetupTarget(home, CONFIG_PATH);
    const cacheTarget = safeSetupTarget(home, CACHE_PATH);
    const configBackup = path.join(transaction, 'cutover-config.before');
    const cacheBackup = path.join(transaction, 'cutover-cache.before');
    copyTarget(configTarget, configBackup, current.config);
    copyTarget(cacheTarget, cacheBackup, current.cache);

    const configRemoval = transactionContext.prepare({
      path: CONFIG_PATH,
      before: current.config,
      after: plan.removed.config,
      backup: path.basename(configBackup),
    });
    const cacheRemoval = transactionContext.prepare({
      path: CACHE_PATH,
      before: current.cache,
      after: null,
      backup: path.basename(cacheBackup),
    });
    const commands = commandPlan(home);
    const evidence = [];
    try {
      evidence.push(runChecked(
        run,
        commands.remove,
        { home, env },
        'Codex Hard Eng plugin removal',
      ));
      if (!same(observe(home, CONFIG_PATH), plan.removed.config) || observe(home, CACHE_PATH) !== null) {
        throw new Error('Codex plugin removal did not match the approved cutover plan.');
      }
      transactionContext.applied(configRemoval);
      transactionContext.applied(cacheRemoval);

      const removedBackup = path.join(transaction, 'cutover-config.removed');
      copyTarget(configTarget, removedBackup, plan.removed.config);
      const configAdd = transactionContext.prepare({
        path: CONFIG_PATH,
        before: plan.removed.config,
        after: plan.after.config,
        backup: path.basename(removedBackup),
      });
      evidence.push(runChecked(
        run,
        commands.add,
        { home, env },
        'Codex standalone MCP add',
      ));
      if (!same(observe(home, CONFIG_PATH), plan.after.config) || observe(home, CACHE_PATH) !== null) {
        throw new Error('Codex standalone MCP wiring did not match the approved cutover plan.');
      }
      transactionContext.applied(configAdd);
      return {
        status: 'PASS',
        action: 'replace',
        changed: true,
        evidence_digest: sha256(evidence.join('\0')),
        applied: collapsedApplied(home, transaction, current),
      };
    } catch (error) {
      restoreTarget(configTarget, configBackup, current.config);
      restoreTarget(cacheTarget, cacheBackup, current.cache);
      throw error;
    }
  }

  return { preview, apply };
}
