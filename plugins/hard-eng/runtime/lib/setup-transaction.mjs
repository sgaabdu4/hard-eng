import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson, digestValue, sha256 } from './canonical.mjs';

export const INSTALL_MANIFEST_SCHEMA = 'hard-eng/install-manifest/v1';
export const ROLLBACK_BUNDLE_SCHEMA = 'hard-eng/rollback-bundle/v1';
const PLAN_SCHEMA = 'hard-eng/setup-plan/v1';
const sourceFiles = [
  'AGENTS.md', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'package.json',
  '.gitignore', '.worktreeinclude', 'scripts/setup.mjs',
];
const sourceDirectories = ['plugins', 'assets/readme'];
const marketplaceTarget = '.agents/plugins/marketplace.json';
const ownedPluginNames = new Set([
  'hard-eng', 'hard-eng-flutter', 'hard-eng-appwrite', 'hard-eng-web',
  'hard-eng-sentry', 'hard-eng-delivery', 'hard-eng-authoring',
]);
function mode(file) {
  return fs.statSync(file).mode & 0o777;
}
function walk(directory, prefix, output) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === '.DS_Store') continue;
    const absolute = path.join(directory, entry.name);
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`Distribution source contains a symlink: ${relative}.`);
    if (entry.isDirectory()) walk(absolute, relative, output);
    else if (entry.isFile()) output.push({ relative, absolute, hash: sha256(fs.readFileSync(absolute)), mode: mode(absolute) });
    else throw new Error(`Distribution source contains an unsupported entry: ${relative}.`);
  }
}
function launcher(version) {
  return `#!/bin/sh\n# hard-eng launcher ${version}\nexec node "$HOME/.agents/plugins/hard-eng/runtime/he.mjs" "$@"\n`;
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
    if (fs.existsSync(absolute)) walk(absolute, relative, files);
  }
  const manifestFile = path.join(sourceRoot, 'plugins', 'hard-eng', '.codex-plugin', 'plugin.json');
  const version = JSON.parse(fs.readFileSync(manifestFile, 'utf8')).version;
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
  return files.sort((left, right) => (left.target ?? `.agents/${left.relative}`).localeCompare(right.target ?? `.agents/${right.relative}`));
}

export function manifestPath(home) {
  return safeSetupTarget(home, '.agents/.hard-eng-install/manifest.json');
}

export function rollbackBundlePath(home, planDigest) {
  if (!/^[a-f0-9]{64}$/.test(planDigest ?? '')) throw new Error('Rollback bundle ID must be a SHA-256 digest.');
  return safeSetupTarget(home, `.agents/.hard-eng-install/backups/${planDigest}`);
}

export function readInstallManifest(home) {
  const file = manifestPath(home);
  if (!fs.existsSync(file)) return null;
  const value = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (value.schema !== INSTALL_MANIFEST_SCHEMA || !Array.isArray(value.entries)) throw new Error('Install ownership manifest is invalid.');
  return value;
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

function parseMarketplace(bytes, label) {
  let value;
  try {
    value = JSON.parse(Buffer.isBuffer(bytes) ? bytes.toString('utf8') : bytes);
  } catch {
    throw new Error(`${label} marketplace is not valid JSON.`);
  }
  if (!value || Array.isArray(value) || typeof value !== 'object' || !Array.isArray(value.plugins)) {
    throw new Error(`${label} marketplace has an invalid shape.`);
  }
  const names = value.plugins.map((entry) => entry?.name);
  if (names.some((name) => typeof name !== 'string') || new Set(names).size !== names.length) {
    throw new Error(`${label} marketplace has invalid or duplicate plugin names.`);
  }
  return value;
}

function ownedMarketplaceEntries(value) {
  return value.plugins.filter((entry) => ownedPluginNames.has(entry.name));
}

function expectedMarketplacePath(name) {
  return `./.agents/plugins/${name}`;
}

function assertOwnedMarketplacePaths(entries, label) {
  for (const entry of entries) {
    if (entry.source?.source !== 'local' || entry.source?.path !== expectedMarketplacePath(entry.name)) {
      throw new Error(`${label} hard-eng plugin name has another owner; resolve the collision before setup.`);
    }
  }
}

function generatedMarketplaceItem(item, value) {
  const generated = `${JSON.stringify(value, null, 2)}\n`;
  return { ...item, generated, hash: sha256(generated), mode: 0o644, merge_allowed: true };
}

function mergeMarketplace(home, item, owned) {
  const current = inspectSetupTarget(item.targetAbsolute);
  if (!current) return item;
  if (current.type !== 'file') throw new Error('Personal marketplace must be a regular file.');
  const source = parseMarketplace(fs.readFileSync(item.absolute), 'Source');
  const existing = parseMarketplace(fs.readFileSync(item.targetAbsolute), 'Existing');
  if (existing.name !== source.name) throw new Error('Existing personal marketplace has another owner.');
  const existingOwned = ownedMarketplaceEntries(existing);
  assertOwnedMarketplacePaths(existingOwned, 'Existing marketplace');
  if (!owned && existingOwned.length > 0) {
    const expected = new Map(ownedMarketplaceEntries(source).map((entry) => [entry.name, canonicalJson(entry)]));
    if (existingOwned.some((entry) => expected.get(entry.name) !== canonicalJson(entry))) {
      throw new Error('Existing hard-eng marketplace name collision requires an owner choice.');
    }
  }
  const unrelated = existing.plugins.filter((entry) => !ownedPluginNames.has(entry.name));
  const merged = {
    ...existing,
    name: source.name,
    interface: existing.interface ?? source.interface,
    plugins: [...unrelated, ...source.plugins],
  };
  if (canonicalJson(merged) === canonicalJson(existing)) {
    const generated = fs.readFileSync(item.targetAbsolute, 'utf8');
    return { ...item, generated, hash: current.hash, mode: current.mode, merge_allowed: true };
  }
  return generatedMarketplaceItem(item, merged);
}

function marketplaceUninstallOperation(home, entry) {
  const target = safeSetupTarget(home, entry.path);
  const current = inspectSetupTarget(target);
  if (!current) return null;
  if (current.type !== 'file') throw new Error('Installed personal marketplace changed type.');
  const value = parseMarketplace(fs.readFileSync(target), 'Installed');
  assertOwnedMarketplacePaths(ownedMarketplaceEntries(value), 'Installed marketplace');
  const unrelated = value.plugins.filter((item) => !ownedPluginNames.has(item.name));
  if (entry.previous_target_hash === null && unrelated.length === 0) return null;
  const generated = `${JSON.stringify({ ...value, plugins: unrelated }, null, 2)}\n`;
  return {
    action: 'write',
    expected_type: 'file',
    path: entry.path,
    source_relative: null,
    generated,
    link_target: null,
    source_hash: sha256(generated),
    current_hash: current.hash,
    mode: current.mode,
    rollback_action: 'restore-current',
  };
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

export function buildSetupPlan({ mode: setupMode, home, sourceRoot, purgeState = false }) {
  const existing = readInstallManifest(home);
  if (setupMode === 'uninstall' && (!existing || existing.status !== 'installed')) throw new Error('Hard Eng is not installed by this manifest.');
  if (setupMode === 'update' && (!existing || existing.status !== 'installed')) throw new Error('Update requires an installed ownership manifest.');
  const oldEntries = new Map((existing?.entries ?? []).map((entry) => [entry.path, entry]));
  const desired = setupMode === 'uninstall' ? [] : collectDistribution(sourceRoot)
    .map((item) => desiredEntry(home, item))
    .map((item) => item.path === marketplaceTarget ? mergeMarketplace(home, item, oldEntries.get(item.path)) : item);
  const desiredPaths = new Set(desired.map((item) => item.path));
  const operations = [];
  const nextEntries = [];

  for (const item of desired) {
    const current = inspectSetupTarget(item.targetAbsolute);
    const owned = oldEntries.get(item.path);
    if (owned) assertOwnedCurrent(owned, current);
    else if (current && !item.merge_allowed && (current.type !== item.expected_type || current.hash !== item.hash)) {
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
    if (setupMode === 'uninstall' && entry.path === marketplaceTarget) {
      const rewrite = marketplaceUninstallOperation(home, entry);
      if (rewrite) operations.push(rewrite);
      else {
        operations.push({
          action: current ? 'remove' : 'noop', expected_type: 'file', path: entry.path,
          source_relative: null, generated: null, link_target: null, source_hash: null,
          current_hash: current?.hash ?? null, mode: null,
          rollback_action: current ? 'restore-current' : 'none',
        });
      }
      continue;
    }
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

  const core = {
    schema: PLAN_SCHEMA,
    mode: setupMode,
    purge_state: purgeState,
    codex_plugin_action: setupMode === 'uninstall' ? 'remove' : 'add-or-refresh',
    target_home_digest: sha256(path.resolve(home)),
    source_digest: digestValue(nextEntries.map(({ path: entryPath, installed_hash }) => ({ path: entryPath, installed_hash }))),
    operations: operations.map(operationView),
  };
  return { ...core, plan_digest: digestValue(core), operations, nextEntries, existing };
}

export function attachMigrationPlan(plan, { legacy, operations, liveCutover, blockers = [] }) {
  const merged = [...plan.operations, ...operations];
  const core = {
    schema: PLAN_SCHEMA,
    mode: 'migrate',
    purge_state: false,
    codex_plugin_action: plan.codex_plugin_action,
    live_cutover: liveCutover,
    target_home_digest: plan.target_home_digest,
    source_digest: plan.source_digest,
    operations: merged.map(operationView),
    legacy,
    migration_blockers: blockers,
  };
  return {
    ...core,
    plan_digest: digestValue(core),
    operations: merged,
    nextEntries: plan.nextEntries,
    existing: plan.existing,
  };
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
    path.join(base, '.treehouse'),
    path.join(base, 'Library'),
    path.join(base, 'Library', 'LaunchAgents'),
  ]);
  while (!stops.has(directory) && directory.startsWith(`${base}${path.sep}`)) {
    if (!fs.existsSync(directory) || fs.readdirSync(directory).length !== 0) break;
    fs.rmdirSync(directory);
    directory = path.dirname(directory);
  }
}
