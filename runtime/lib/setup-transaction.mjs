import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson, digestValue, sha256 } from './canonical.mjs';
import {
  INSTALL_MANIFEST_SCHEMA,
  validateInstallManifest,
} from './install-manifest.mjs';
import {
  BOOTSTRAP_PATH,
  E2E_CACHE_PATH,
  neutralizeBootstrap,
  validateCanonicalTeach,
  validateE2eCache,
} from './live-cutover-owned.mjs';
import { canAdoptPublishedSourceEntry, observePublishedSelfHostedSource } from './setup-source-checkout.mjs';

export { INSTALL_MANIFEST_SCHEMA } from './install-manifest.mjs';
export const ROLLBACK_BUNDLE_SCHEMA = 'hard-eng/rollback-bundle/v1';
const PLAN_SCHEMA = 'hard-eng/setup-plan/v1';
const sourceFiles = [
  'AGENTS.md', 'PRODUCT.md', 'DESIGN.md', 'README.md', 'LICENSE',
  'THIRD_PARTY_NOTICES.md', 'package.json', '.gitignore', '.gitmodules',
  '.worktreeinclude',
];
const sourceDirectories = [
  '.github', 'assets/readme', 'hooks', 'runtime', 'scripts', 'skills',
  'tests', 'vendor',
];
function mode(file) {
  return fs.statSync(file).mode & 0o777;
}
function walk(directory, prefix, output, sourceRoot) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === '.DS_Store' || entry.name === '.git') continue;
    const absolute = path.join(directory, entry.name);
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isSymbolicLink()) {
      const linkTarget = fs.readlinkSync(absolute);
      const resolved = path.resolve(path.dirname(absolute), linkTarget);
      const root = path.resolve(sourceRoot);
      if (path.isAbsolute(linkTarget) || (resolved !== root && !resolved.startsWith(`${root}${path.sep}`))) {
        throw new Error(`Distribution source symlink escapes the native source: ${relative}.`);
      }
      output.push({ relative, link_target: linkTarget, hash: sha256(`symlink\0${linkTarget}`), mode: null });
    } else if (entry.isDirectory()) walk(absolute, relative, output, sourceRoot);
    else if (entry.isFile()) output.push({ relative, absolute, hash: sha256(fs.readFileSync(absolute)), mode: mode(absolute) });
    else throw new Error(`Distribution source contains an unsupported entry: ${relative}.`);
  }
}
function launcher(version) {
  return `#!/bin/sh\n# hard-eng launcher ${version}\nexec node "$HOME/.agents/runtime/he.mjs" "$@"\n`;
}
export function collectDistribution(sourceRoot) {
  const files = [];
  for (const relative of sourceFiles) {
    const absolute = path.join(sourceRoot, relative);
    if (!fs.existsSync(absolute)) continue;
    const stat = fs.lstatSync(absolute);
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`Distribution source is not a regular file: ${relative}.`);
    files.push({ relative, absolute, hash: sha256(fs.readFileSync(absolute)), mode: mode(absolute) });
  }
  for (const relative of sourceDirectories) {
    const absolute = path.join(sourceRoot, relative);
    if (fs.existsSync(absolute)) walk(absolute, relative, files, sourceRoot);
  }
  const version = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8')).version;
  if (typeof version !== 'string' || !version) throw new Error('Root package version is invalid.');
  const body = launcher(version);
  files.push({
    relative: null,
    target: '.local/bin/he',
    generated: body,
    hash: sha256(body),
    mode: 0o755,
  });
  files.push({
    relative: null,
    target: '.codex/AGENTS.md',
    link_target_home: '.agents/AGENTS.md',
    mode: null,
  });
  files.push({
    relative: null,
    target: '.codex/hooks.json',
    link_target_home: '.agents/hooks/hooks.json',
    mode: null,
  });
  return files.sort((left, right) => (left.target ?? `.agents/${left.relative}`).localeCompare(right.target ?? `.agents/${right.relative}`));
}

export function manifestPath(home) {
  return safeSetupTarget(home, '.agents/.hard-eng-install/manifest.json');
}

export function rollbackBundlePath(home, planDigest) {
  if (!/^[a-f0-9]{64}$/.test(planDigest ?? '')) throw new Error('Rollback bundle ID must be a SHA-256 digest.');
  return safeSetupTarget(home, `.agents/.hard-eng-install/backups/${planDigest}`);
}

export function readInstallManifestRecord(home) {
  const file = manifestPath(home);
  if (!fs.existsSync(file)) return null;
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 4 * 1024 * 1024) {
    throw new Error('Install manifest file is unsafe or oversized.');
  }
  const bytes = fs.readFileSync(file);
  const value = JSON.parse(bytes.toString('utf8'));
  validateInstallManifest(value);
  return { value, bytes, hash: sha256(bytes) };
}

export function readInstallManifest(home) {
  return readInstallManifestRecord(home)?.value ?? null;
}

export function inspectSetupTarget(target) {
  let stat;
  try {
    stat = fs.lstatSync(target);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
  if (stat.isSymbolicLink()) {
    const link_target = fs.readlinkSync(target);
    return { type: 'symlink', hash: sha256(`symlink\0${link_target}`), mode: null, link_target };
  }
  if (stat.isDirectory()) {
    const entries = [];
    function inspectDirectory(directory, prefix = '') {
      for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
        const absolute = path.join(directory, entry.name);
        const relative = path.posix.join(prefix, entry.name);
        const child = fs.lstatSync(absolute);
        if (child.isSymbolicLink()) {
          const linkTarget = fs.readlinkSync(absolute);
          entries.push({ path: relative, type: 'symlink', hash: sha256(`symlink\0${linkTarget}`) });
        } else if (child.isDirectory()) {
          entries.push({ path: relative, type: 'directory', mode: child.mode & 0o777 });
          inspectDirectory(absolute, relative);
        } else if (child.isFile()) {
          entries.push({
            path: relative,
            type: 'file',
            mode: child.mode & 0o777,
            hash: sha256(fs.readFileSync(absolute)),
          });
        } else {
          throw new Error(`Install target directory contains an unsupported entry: ${relative}.`);
        }
      }
    }
    inspectDirectory(target);
    return { type: 'directory', hash: digestValue(entries), mode: stat.mode & 0o777, entries: entries.length };
  }
  if (!stat.isFile()) throw new Error('Install target is not a regular file or symlink.');
  return { type: 'file', hash: sha256(fs.readFileSync(target)), mode: stat.mode & 0o777 };
}

export function safeSetupTarget(home, relative) {
  if (
    typeof relative !== 'string'
    || !relative
    || path.isAbsolute(relative)
    || relative.includes('\\')
    || path.posix.normalize(relative) !== relative
    || relative.split('/').some((part) => !part || part === '..')
  ) throw new Error('Setup target path is unsafe.');
  const base = fs.realpathSync(home);
  const parts = relative.split('/');
  let current = base;
  for (const part of parts.slice(0, -1)) {
    current = path.join(current, part);
    let stat;
    try {
      stat = fs.lstatSync(current);
    } catch (error) {
      if (error.code === 'ENOENT') break;
      throw error;
    }
    if (stat.isSymbolicLink()) throw new Error(`Setup target parent is a symlink: ${relative}.`);
    if (!stat.isDirectory()) throw new Error(`Setup target parent is not a directory: ${relative}.`);
  }
  const target = path.join(base, ...parts);
  if (!target.startsWith(`${base}${path.sep}`)) throw new Error('Setup target escapes the selected home.');
  return target;
}

function desiredEntry(home, source) {
  const relative = source.target ?? `.agents/${source.relative}`;
  if (source.link_target_home) {
    const linkTarget = path.join(path.resolve(home), ...source.link_target_home.split('/'));
    return {
      ...source,
      path: relative,
      expected_type: 'symlink',
      link_target: linkTarget,
      hash: sha256(`symlink\0${linkTarget}`),
      targetAbsolute: safeSetupTarget(home, relative),
    };
  }
  if (source.link_target !== undefined) {
    return {
      ...source,
      path: relative,
      expected_type: 'symlink',
      targetAbsolute: safeSetupTarget(home, relative),
    };
  }
  return {
    ...source,
    path: relative,
    expected_type: 'file',
    targetAbsolute: safeSetupTarget(home, relative),
  };
}

function assertOwnedCurrent(entry, current) {
  if (current && current.hash !== entry.installed_hash) throw new Error(`Modified owned file blocks setup: ${entry.path}.`);
}

function operationView(operation) {
  return {
    action: operation.action,
    path: operation.path,
    expected_type: operation.expected_type ?? 'file',
    source_hash: operation.source_hash ?? null,
    current_hash: operation.current_hash ?? null,
    mode: operation.mode ?? null,
    rollback_action: operation.rollback_action,
  };
}

const setupPlanCoreKeys = [
  'schema', 'mode', 'purge_state', 'codex_mcp_action', 'codex_mcp',
  'live_cutover', 'codex_cutover', 'target_home_digest', 'source_version',
  'source_digest', 'existing_manifest_hash', 'source_checkout_adoption',
];

export function buildSetupPlanCore(plan, additions = {}) {
  const core = {};
  for (const key of setupPlanCoreKeys) {
    if (Object.hasOwn(plan, key)) core[key] = plan[key];
  }
  core.operations = plan.operations.map(operationView);
  return { ...core, ...additions };
}

function validateCustomAgentParity(sourceRoot, profileName, parity) {
  const expectedProofId = `custom-agent/${profileName.slice(0, -'.toml'.length)}`;
  if (
    !parity
    || JSON.stringify(Object.keys(parity).sort()) !== JSON.stringify(['owners', 'proof_id', 'required_terms'])
    || parity.proof_id !== expectedProofId
    || !Array.isArray(parity.owners)
    || parity.owners.length < 1
    || new Set(parity.owners).size !== parity.owners.length
    || !Array.isArray(parity.required_terms)
    || parity.required_terms.length < 1
  ) throw new Error(`Custom-agent parity proof is invalid: ${profileName}.`);
  const ownerText = parity.owners.map((relative) => {
    if (
      typeof relative !== 'string'
      || path.isAbsolute(relative)
      || relative.split('/').includes('..')
      || !relative.endsWith('.md')
    ) throw new Error(`Custom-agent parity owner is invalid: ${profileName}.`);
    const file = path.resolve(sourceRoot, relative);
    if (!file.startsWith(`${path.resolve(sourceRoot)}${path.sep}`) || !fs.existsSync(file)) {
      throw new Error(`Custom-agent parity owner is missing: ${profileName}.`);
    }
    const stat = fs.statSync(file);
    if (!stat.isFile() || stat.size > 1024 * 1024) {
      throw new Error(`Custom-agent parity owner is unsafe: ${profileName}.`);
    }
    return fs.readFileSync(file, 'utf8');
  }).join('\n').toLocaleLowerCase('en-US');
  for (const term of parity.required_terms) {
    if (
      typeof term !== 'string'
      || !term.trim()
      || term.length > 80
      || /[\r\n\0]/.test(term)
      || !ownerText.includes(term.toLocaleLowerCase('en-US'))
    ) throw new Error(`Custom-agent parity obligation is unproven: ${profileName}.`);
  }
  return {
    proof_id: parity.proof_id,
    owners: [...parity.owners],
    required_terms: [...parity.required_terms],
  };
}

function cutoverLinkMap(home, sourceRoot, codexCutover, desiredPaths) {
  if (
    !Array.isArray(codexCutover.skill_links)
    || !Array.isArray(codexCutover.replace_links)
    || !Array.isArray(codexCutover.remove_links)
  ) throw new Error('Codex cutover link ledger is invalid.');
  const backupLinks = codexCutover.remove_links.filter((entry) => (
    /^\.codex\/(?:AGENTS\.md|hooks\.json)\.backup\.\d{8,}$/.test(entry?.path ?? '')
  ));
  if (codexCutover.skill_links.length !== 46 || backupLinks.length !== 9) {
    throw new Error('Codex cutover link ledger does not match the approved 46 skill links and nine backup links.');
  }

  const seen = new Set();
  const replacements = new Map();
  const removals = [];
  const ownedOperations = [];
  const groups = [
    {
      entries: codexCutover.skill_links,
      accepts: (entryPath) => /^\.codex\/skills\/[^/]+$/.test(entryPath),
      action: 'remove',
    },
    {
      entries: codexCutover.replace_links,
      accepts: (entryPath) => entryPath === '.codex/hooks.json' && desiredPaths.has(entryPath),
      action: 'replace',
    },
    {
      entries: codexCutover.remove_links,
      accepts: (entryPath) => entryPath === '.codex/mcp-config.json'
        || /^\.codex\/(?:AGENTS\.md|hooks\.json)\.backup\.\d{8,}$/.test(entryPath),
      action: 'remove',
    },
  ];

  for (const group of groups) {
    for (const link of group.entries) {
      if (
        typeof link?.path !== 'string'
        || !group.accepts(link.path)
        || link.before?.type !== 'symlink'
        || !/^[a-f0-9]{64}$/.test(link.before.hash ?? '')
        || seen.has(link.path)
      ) throw new Error('Codex cutover link ledger contains an invalid entry.');
      seen.add(link.path);
      const current = inspectSetupTarget(safeSetupTarget(home, link.path));
      if (!current || current.type !== 'symlink' || current.hash !== link.before.hash) {
        throw new Error(`Codex cutover link changed after approval: ${link.path}.`);
      }
      if (group.action === 'replace') replacements.set(link.path, link);
      else {
        if (desiredPaths.has(link.path)) {
          throw new Error('Codex cutover removal conflicts with the native distribution.');
        }
        removals.push(link);
      }
    }
  }

  const bootstrap = codexCutover.bootstrap_path;
  if (bootstrap !== null) {
    if (
      !bootstrap
      || JSON.stringify(Object.keys(bootstrap).sort()) !== JSON.stringify(['after', 'before', 'path'])
      || bootstrap.path !== BOOTSTRAP_PATH
      || bootstrap.before?.type !== 'file'
      || bootstrap.after?.type !== 'file'
      || !/^[a-f0-9]{64}$/.test(bootstrap.before.hash ?? '')
      || !/^[a-f0-9]{64}$/.test(bootstrap.after.hash ?? '')
      || !Number.isInteger(bootstrap.before.mode)
      || bootstrap.before.mode !== bootstrap.after.mode
      || desiredPaths.has(bootstrap.path)
    ) throw new Error('Codex cutover bootstrap ledger is invalid.');
    const target = safeSetupTarget(home, bootstrap.path);
    const current = inspectSetupTarget(target);
    if (!current || current.type !== 'file' || current.hash !== bootstrap.before.hash || current.mode !== bootstrap.before.mode) {
      throw new Error('Hard Eng bootstrap owner changed after cutover approval.');
    }
    const generated = neutralizeBootstrap(fs.readFileSync(target));
    if (!generated || sha256(generated) !== bootstrap.after.hash) {
      throw new Error('Hard Eng bootstrap replacement does not match the approved cutover.');
    }
    ownedOperations.push({
      action: 'write', expected_type: 'file', path: bootstrap.path,
      source_relative: null, generated, link_target: null,
      source_hash: bootstrap.after.hash, current_hash: current.hash,
      mode: current.mode, rollback_action: 'restore-current',
    });
  }

  const cache = codexCutover.e2e_cache;
  if (cache !== null) {
    if (
      !cache
      || JSON.stringify(Object.keys(cache).sort()) !== JSON.stringify(['before', 'path'])
      || cache.path !== E2E_CACHE_PATH
      || cache.before?.type !== 'directory'
      || !/^[a-f0-9]{64}$/.test(cache.before.hash ?? '')
      || !Number.isInteger(cache.before.mode)
      || desiredPaths.has(cache.path)
    ) throw new Error('Codex cutover E2E-cache ledger is invalid.');
    const target = safeSetupTarget(home, cache.path);
    const current = inspectSetupTarget(target);
    if (!current || current.type !== 'directory' || current.hash !== cache.before.hash || current.mode !== cache.before.mode) {
      throw new Error('Hard Eng E2E cache changed after cutover approval.');
    }
    validateE2eCache(target);
    ownedOperations.push({
      action: 'remove', expected_type: 'directory', path: cache.path,
      source_relative: null, generated: null, link_target: null,
      source_hash: null, current_hash: current.hash, mode: null,
      rollback_action: 'restore-current',
    });
  }

  if (!Array.isArray(codexCutover.custom_agents) || codexCutover.custom_agents.length !== 25) {
    throw new Error('Codex cutover custom-agent ledger is invalid.');
  }
  const agentProofs = {};
  for (const agent of codexCutover.custom_agents) {
    if (
      !agent
      || JSON.stringify(Object.keys(agent).sort()) !== JSON.stringify(['before', 'parity', 'path'])
      || !/^\.codex\/agents\/[A-Za-z0-9-]+\.toml$/.test(agent.path ?? '')
      || agent.before?.type !== 'file'
      || !/^[a-f0-9]{64}$/.test(agent.before.hash ?? '')
      || !Number.isInteger(agent.before.mode)
      || seen.has(agent.path)
      || desiredPaths.has(agent.path)
    ) throw new Error('Codex cutover custom-agent ledger contains an invalid entry.');
    const profileName = path.posix.basename(agent.path);
    const parity = validateCustomAgentParity(sourceRoot, profileName, agent.parity);
    seen.add(agent.path);
    const current = inspectSetupTarget(safeSetupTarget(home, agent.path));
    if (!current || current.type !== 'file' || current.hash !== agent.before.hash || current.mode !== agent.before.mode) {
      throw new Error(`Custom-agent profile changed after cutover approval: ${agent.path}.`);
    }
    agentProofs[profileName] = { hash: agent.before.hash, ...parity };
    ownedOperations.push({
      action: 'remove', expected_type: 'file', path: agent.path,
      source_relative: null, generated: null, link_target: null,
      source_hash: null, current_hash: current.hash, mode: null,
      rollback_action: 'restore-current',
    });
  }

  const teach = codexCutover.duplicate_teach;
  const teachFiles = [
    'GLOSSARY-FORMAT.md', 'LEARNING-RECORD-FORMAT.md', 'MISSION-FORMAT.md',
    'RESOURCES-FORMAT.md', 'SKILL.md',
  ];
  if (
    !teach
    || JSON.stringify(Object.keys(teach).sort()) !== JSON.stringify(['before', 'files', 'path'])
    || teach.path !== '.codex/skills/teach'
    || teach.before?.type !== 'directory'
    || !/^[a-f0-9]{64}$/.test(teach.before.hash ?? '')
    || !Number.isInteger(teach.before.mode)
    || JSON.stringify(teach.files) !== JSON.stringify(teachFiles)
    || seen.has(teach.path)
    || desiredPaths.has(teach.path)
  ) throw new Error('Codex cutover duplicate-Teach ledger is invalid.');
  const teachCurrent = inspectSetupTarget(safeSetupTarget(home, teach.path));
  if (
    !teachCurrent
    || teachCurrent.type !== 'directory'
    || teachCurrent.hash !== teach.before.hash
    || teachCurrent.mode !== teach.before.mode
  ) throw new Error('Duplicate Teach owner changed after cutover approval.');
  validateCanonicalTeach(sourceRoot);
  seen.add(teach.path);
  ownedOperations.push({
    action: 'remove', expected_type: 'directory', path: teach.path,
    source_relative: null, generated: null, link_target: null,
    source_hash: null, current_hash: teachCurrent.hash, mode: null,
    rollback_action: 'restore-current',
  });

  const retirementDigest = digestValue({
    legacy_skill_links: Object.fromEntries(codexCutover.skill_links
      .map((entry) => [path.posix.basename(entry.path), entry.before.hash])
      .sort(([left], [right]) => left.localeCompare(right))),
    legacy_backup_links: Object.fromEntries(backupLinks
      .map((entry) => [entry.path, entry.before.hash])
      .sort(([left], [right]) => left.localeCompare(right))),
    duplicate_teach: { path: teach.path, hash: teach.before.hash, files: teach.files },
    custom_agents: Object.fromEntries(Object.entries(agentProofs).sort(([left], [right]) => left.localeCompare(right))),
  });
  if (retirementDigest !== codexCutover.retirement_inventory_digest) {
    throw new Error('Codex cutover retirement inventory digest is invalid.');
  }
  return { replacements, removals, ownedOperations };
}

export function buildSetupPlan({
  mode: setupMode,
  home,
  sourceRoot,
  purgeState = false,
  codexMcp,
  codexCutover = null,
  liveCutover = false,
}) {
  if (!codexMcp || !['PASS', 'NOT_CONFIGURED', 'MIGRATION_REQUIRED'].includes(codexMcp.status)) {
    throw new Error('Setup requires a safe Codex MCP observation.');
  }
  if (!/^[a-f0-9]{64}$/.test(codexMcp.evidence_digest ?? '')) {
    throw new Error('Codex MCP observation has no valid evidence digest.');
  }
  const replacingInstalledOwner = codexMcp.status === 'MIGRATION_REQUIRED';
  if (replacingInstalledOwner) {
    const { evidence_digest: cutoverDigest, ...cutoverCore } = codexCutover ?? {};
    if (setupMode !== 'migrate' || liveCutover !== true) {
      throw new Error('The installed Hard Eng owner requires the explicit migrate --live-cutover route.');
    }
    if (
      codexCutover?.schema !== 'hard-eng/codex-cutover/v2'
      || codexCutover.target_home_digest !== sha256(path.resolve(home))
      || codexCutover.wiring_evidence_digest !== codexMcp.evidence_digest
      || !/^[a-f0-9]{64}$/.test(cutoverDigest ?? '')
      || codexCutover.legacy_control_plane?.status !== 'PASS'
      || !/^[a-f0-9]{64}$/.test(codexCutover.legacy_control_plane?.evidence_digest ?? '')
      || digestValue(cutoverCore) !== cutoverDigest
    ) throw new Error('Codex cutover evidence does not match the selected owner.');
  } else if (codexCutover !== null || liveCutover) {
    throw new Error('Codex cutover evidence is valid only for the exact installed owner.');
  }
  const existingRecord = readInstallManifestRecord(home);
  const existing = existingRecord?.value ?? null;
  const targetHomeDigest = sha256(path.resolve(home));
  const sourceCheckout = ['update', 'migrate'].includes(setupMode)
    ? observePublishedSelfHostedSource({ home, sourceRoot }) : null;
  if (existing && existing.target_home_digest !== targetHomeDigest) {
    throw new Error('Install manifest belongs to another target home.');
  }
  if (setupMode === 'uninstall' && (!existing || existing.status !== 'installed')) throw new Error('Hard Eng is not installed by this manifest.');
  if (setupMode === 'update' && (!existing || existing.status !== 'installed')) throw new Error('Update requires an installed ownership manifest.');
  const sourceVersion = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8')).version;
  if (typeof sourceVersion !== 'string' || !sourceVersion) throw new Error('Root package version is invalid.');
  const oldEntries = new Map((existing?.entries ?? []).map((entry) => [entry.path, entry]));
  const desired = setupMode === 'uninstall' ? [] : collectDistribution(sourceRoot)
    .map((item) => desiredEntry(home, item));
  const desiredPaths = new Set(desired.map((item) => item.path));
  const cutoverLinks = replacingInstalledOwner
    ? cutoverLinkMap(home, sourceRoot, codexCutover, desiredPaths)
    : { replacements: new Map(), removals: [], ownedOperations: [] };
  const operations = [];
  const nextEntries = [];
  const adoptedPaths = [];

  for (const item of desired) {
    const current = inspectSetupTarget(item.targetAbsolute);
    const owned = oldEntries.get(item.path);
    const cutoverReplacement = cutoverLinks.replacements.get(item.path);
    const adopted = canAdoptPublishedSourceEntry({ sourceCheckout, sourceRoot, item, current, owned });
    if (owned && !adopted) assertOwnedCurrent(owned, current);
    if (adopted) adoptedPaths.push(item.path);
    else if (!owned &&
      current
      && !item.merge_allowed
      && (current.type !== item.expected_type || current.hash !== item.hash)
      && !(
        cutoverReplacement?.before?.type === current.type
        && cutoverReplacement.before.hash === current.hash
      )
    ) {
      throw new Error(`Unknown existing file blocks setup: ${item.path}.`);
    }
    const action = current?.hash === item.hash && current?.mode === item.mode ? 'noop' : 'write';
    operations.push({
      action,
      expected_type: item.expected_type,
      path: item.path,
      source_relative: item.relative,
      generated: item.generated ?? null,
      link_target: item.link_target ?? null,
      source_hash: item.hash,
      current_hash: current?.hash ?? null,
      mode: item.mode,
      rollback_action: current ? 'restore-current' : 'remove-created',
    });
    nextEntries.push({
      path: item.path,
      expected_type: item.expected_type,
      source_hash: item.hash,
      installed_hash: item.hash,
      previous_target_hash: owned?.previous_target_hash
        ?? (current?.hash && current.hash !== item.hash ? current.hash : null),
      rollback_action: current && current.hash !== item.hash ? 'restore-backup' : owned?.rollback_action ?? 'remove',
      mode: item.mode,
    });
  }

  for (const entry of oldEntries.values()) {
    if (desiredPaths.has(entry.path)) continue;
    const target = safeSetupTarget(home, entry.path);
    const current = inspectSetupTarget(target);
    assertOwnedCurrent(entry, current);
    operations.push({
      action: current ? 'remove' : 'noop',
      expected_type: entry.expected_type ?? 'file',
      path: entry.path,
      source_relative: null,
      generated: null,
      source_hash: null,
      current_hash: current?.hash ?? null,
      mode: null,
      rollback_action: current ? 'restore-current' : 'none',
    });
  }

  if (replacingInstalledOwner) {
    operations.push(...cutoverLinks.ownedOperations);
    for (const link of cutoverLinks.removals) {
      const current = inspectSetupTarget(safeSetupTarget(home, link.path));
      operations.push({
        action: 'remove',
        expected_type: 'symlink',
        path: link.path,
        source_relative: null,
        generated: null,
        link_target: null,
        source_hash: null,
        current_hash: current.hash,
        mode: null,
        rollback_action: 'restore-current',
      });
    }
  }

  const desiredCodexMcpConfigured = setupMode !== 'uninstall';
  const codexMcpAction = replacingInstalledOwner
    ? 'cutover'
    : desiredCodexMcpConfigured
    ? codexMcp.status === 'PASS' ? 'none' : 'add'
    : codexMcp.status === 'PASS' ? 'remove' : 'none';
  const planFields = {
    schema: PLAN_SCHEMA,
    mode: setupMode,
    purge_state: purgeState,
    codex_mcp_action: codexMcpAction,
    codex_mcp: {
      before_status: codexMcp.status,
      before_evidence_digest: codexMcp.evidence_digest,
      desired_configured: desiredCodexMcpConfigured,
    },
    ...(replacingInstalledOwner ? { live_cutover: true, codex_cutover: codexCutover } : {}),
    target_home_digest: targetHomeDigest,
    source_version: sourceVersion,
    source_digest: digestValue(nextEntries.map(({ path: entryPath, installed_hash }) => ({ path: entryPath, installed_hash }))),
    existing_manifest_hash: existingRecord?.hash ?? null,
    ...(sourceCheckout ? { source_checkout_adoption: {
      ...sourceCheckout, adopted_path_count: adoptedPaths.length,
      adopted_paths_digest: digestValue(adoptedPaths.sort()),
    } } : {}),
    operations,
  };
  const core = buildSetupPlanCore(planFields);
  return { ...core, plan_digest: digestValue(core), operations, nextEntries, existing };
}

export function mkdirPrivate(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  fs.chmodSync(directory, 0o700);
}

export function atomicWrite(file, bytes, fileMode) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o755 });
  const temporary = `${file}.tmp-${process.pid}-${randomBytes(5).toString('hex')}`;
  const fd = fs.openSync(temporary, 'wx', fileMode);
  try {
    fs.writeFileSync(fd, bytes);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  fs.renameSync(temporary, file);
  fs.chmodSync(file, fileMode);
}

export function pruneEmptyParents(file, home) {
  let directory = path.dirname(file);
  const base = fs.realpathSync(home);
  const stops = new Set([
    base,
    path.join(base, '.agents'),
    path.join(base, '.local'),
    path.join(base, '.codex'),
    path.join(base, '.cache'),
    path.join(base, '.config'),
    path.join(base, 'Library'),
    path.join(base, 'Library', 'LaunchAgents'),
  ]);
  while (!stops.has(directory) && directory.startsWith(`${base}${path.sep}`)) {
    if (!fs.existsSync(directory) || fs.readdirSync(directory).length !== 0) break;
    fs.rmdirSync(directory);
    directory = path.dirname(directory);
  }
}
