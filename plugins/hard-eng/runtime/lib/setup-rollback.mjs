import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { digestValue, sha256 } from './canonical.mjs';
import {
  INSTALL_MANIFEST_SCHEMA,
  ROLLBACK_BUNDLE_SCHEMA,
  atomicWrite,
  inspectSetupTarget,
  manifestPath,
  pruneEmptyParents,
  rollbackBundlePath,
  safeSetupTarget,
} from './setup-transaction.mjs';

const ROLLBACK_PLAN_SCHEMA = 'hard-eng/setup-rollback-plan/v1';
const receiptKeys = new Set([
  'schema', 'bundle_id', 'source_mode', 'source_plan_digest', 'target_home_digest',
  'previous_manifest', 'entries', 'created_at',
]);
const entryKeys = new Set(['path', 'before', 'after', 'backup']);
const snapshotKeys = new Set(['type', 'hash', 'mode', 'link_target']);

function assertKeys(value, allowed, label) {
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(`${label} must be an object.`);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
  }
}

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function validateSnapshot(value, label) {
  if (value === null) return;
  assertKeys(value, snapshotKeys, label);
  if (!['file', 'directory', 'symlink'].includes(value.type)) throw new Error(`${label} type is invalid.`);
  assertDigest(value.hash, `${label} hash`);
  if (value.type === 'symlink') {
    if (value.mode !== null || typeof value.link_target !== 'string' || value.link_target.length > 4096) {
      throw new Error(`${label} symlink metadata is invalid.`);
    }
  } else {
    if (!Number.isInteger(value.mode) || value.mode < 0 || value.mode > 0o777 || value.link_target !== undefined) {
      throw new Error(`${label} file metadata is invalid.`);
    }
  }
}

function sameSnapshot(actual, expected) {
  if (!actual || !expected) return actual === expected;
  return actual.type === expected.type
    && actual.hash === expected.hash
    && (actual.mode ?? null) === expected.mode
    && (actual.link_target ?? null) === (expected.link_target ?? null);
}

function validateBackupData(bundle, entry) {
  if (!entry.before || entry.before.type === 'symlink') {
    if (entry.backup !== null) throw new Error(`Rollback entry backup is unexpected: ${entry.path}.`);
    return null;
  }
  if (!/^data\/[0-9]+$/.test(entry.backup ?? '')) throw new Error(`Rollback entry backup path is invalid: ${entry.path}.`);
  const target = path.join(bundle, ...entry.backup.split('/'));
  const base = path.resolve(bundle);
  if (!path.resolve(target).startsWith(`${base}${path.sep}`)) throw new Error('Rollback backup escapes its bundle.');
  const observed = inspectSetupTarget(target);
  if (!observed || observed.type !== entry.before.type || observed.hash !== entry.before.hash) {
    throw new Error(`Rollback backup data is stale or corrupt: ${entry.path}.`);
  }
  return target;
}

function readBundle(home, backupPlanDigest) {
  const bundle = rollbackBundlePath(home, backupPlanDigest);
  const bundleStat = fs.lstatSync(bundle);
  if (!bundleStat.isDirectory() || bundleStat.isSymbolicLink()) throw new Error('Rollback bundle root is unsafe.');
  const receiptFile = path.join(bundle, 'receipt.json');
  const receiptStat = fs.lstatSync(receiptFile);
  if (!receiptStat.isFile() || receiptStat.isSymbolicLink() || receiptStat.size > 4 * 1024 * 1024) {
    throw new Error('Rollback receipt is unsafe or oversized.');
  }
  const receiptBytes = fs.readFileSync(receiptFile);
  const receiptDigest = sha256(receiptBytes);
  const receipt = JSON.parse(receiptBytes.toString('utf8'));
  assertKeys(receipt, receiptKeys, 'Rollback receipt');
  if (receipt.schema !== ROLLBACK_BUNDLE_SCHEMA) throw new Error('Rollback receipt schema is unsupported.');
  if (receipt.bundle_id !== backupPlanDigest) throw new Error('Rollback receipt identity does not match its bundle.');
  assertDigest(receipt.source_plan_digest, 'Rollback source-plan digest');
  assertDigest(receipt.target_home_digest, 'Rollback target-home digest');
  if (!['install', 'update', 'migrate', 'uninstall'].includes(receipt.source_mode)) throw new Error('Rollback source mode is invalid.');
  if (!Number.isFinite(Date.parse(receipt.created_at))) throw new Error('Rollback receipt timestamp is invalid.');
  assertKeys(receipt.previous_manifest, new Set(['present', 'hash', 'backup']), 'Rollback previous manifest');
  if (typeof receipt.previous_manifest.present !== 'boolean') throw new Error('Rollback previous-manifest presence is invalid.');
  if (receipt.previous_manifest.present) {
    assertDigest(receipt.previous_manifest.hash, 'Rollback previous-manifest hash');
    if (receipt.previous_manifest.backup !== 'previous-manifest.json') throw new Error('Rollback previous-manifest backup is invalid.');
    const previous = path.join(bundle, receipt.previous_manifest.backup);
    const stat = fs.lstatSync(previous);
    if (!stat.isFile() || stat.isSymbolicLink() || sha256(fs.readFileSync(previous)) !== receipt.previous_manifest.hash) {
      throw new Error('Rollback previous manifest is stale or corrupt.');
    }
  } else if (receipt.previous_manifest.hash !== null || receipt.previous_manifest.backup !== null) {
    throw new Error('Rollback absent previous-manifest metadata is invalid.');
  }
  if (!Array.isArray(receipt.entries) || receipt.entries.length === 0 || receipt.entries.length > 10_000) {
    throw new Error('Rollback receipt entry ledger is invalid.');
  }
  const seen = new Set();
  const entries = receipt.entries.map((entry) => {
    assertKeys(entry, entryKeys, 'Rollback entry');
    safeSetupTarget(home, entry.path);
    if (seen.has(entry.path)) throw new Error(`Rollback receipt contains duplicate path: ${entry.path}.`);
    seen.add(entry.path);
    validateSnapshot(entry.before, `Rollback before snapshot for ${entry.path}`);
    validateSnapshot(entry.after, `Rollback after snapshot for ${entry.path}`);
    const backupAbsolute = validateBackupData(bundle, entry);
    return { ...entry, backupAbsolute };
  });
  return { bundle, receipt, receiptBytes, receiptDigest, entries };
}

function rollbackOperation(entry) {
  const action = entry.before ? `restore-${entry.before.type}` : 'remove-created';
  return {
    action,
    path: entry.path,
    expected_type: entry.after?.type ?? null,
    current_hash: entry.after?.hash ?? null,
    source_hash: entry.before?.hash ?? null,
    rollback_action: 'restore-cutover-state',
    before: entry.before,
    after: entry.after,
    backup: entry.backup,
    backupAbsolute: entry.backupAbsolute,
  };
}

function operationView(operation) {
  return {
    action: operation.action,
    path: operation.path,
    expected_type: operation.expected_type,
    current_hash: operation.current_hash,
    source_hash: operation.source_hash,
    rollback_action: operation.rollback_action,
  };
}

export function buildRollbackPlan({ home, backupPlanDigest }) {
  const bundle = readBundle(home, backupPlanDigest);
  if (sha256(path.resolve(home)) !== bundle.receipt.target_home_digest) throw new Error('Rollback bundle belongs to another target home.');
  const currentManifestFile = manifestPath(home);
  if (!fs.existsSync(currentManifestFile)) throw new Error('Rollback bundle is not the current installed generation.');
  const currentManifestBytes = fs.readFileSync(currentManifestFile);
  const currentManifest = JSON.parse(currentManifestBytes.toString('utf8'));
  if (
    currentManifest.rollback_bundle?.bundle_id !== backupPlanDigest
    || currentManifest.rollback_bundle?.receipt_digest !== bundle.receiptDigest
  ) throw new Error('Rollback bundle is not the current installed generation.');
  const operations = bundle.entries.map(rollbackOperation);
  for (const operation of operations) {
    const current = inspectSetupTarget(safeSetupTarget(home, operation.path));
    if (!sameSnapshot(current, operation.after)) throw new Error(`Rollback target changed after cutover: ${operation.path}.`);
  }
  let previousPluginInstalled = false;
  if (bundle.receipt.previous_manifest.present) {
    const previous = JSON.parse(fs.readFileSync(path.join(bundle.bundle, 'previous-manifest.json'), 'utf8'));
    if (previous.schema !== INSTALL_MANIFEST_SCHEMA || !['installed', 'uninstalled'].includes(previous.status)) {
      throw new Error('Rollback previous install manifest is invalid.');
    }
    previousPluginInstalled = previous.status === 'installed';
  }
  const core = {
    schema: ROLLBACK_PLAN_SCHEMA,
    mode: 'rollback',
    backup_bundle_id: backupPlanDigest,
    source_plan_digest: bundle.receipt.source_plan_digest,
    target_home_digest: bundle.receipt.target_home_digest,
    receipt_digest: bundle.receiptDigest,
    current_manifest_hash: sha256(currentManifestBytes),
    previous_plugin_installed: previousPluginInstalled,
    codex_plugin_action: previousPluginInstalled ? 'add-or-refresh' : 'remove',
    operations: operations.map(operationView),
  };
  return {
    ...core,
    plan_digest: digestValue(core),
    operations,
    receipt: bundle.receipt,
    bundle: bundle.bundle,
  };
}

function removePath(target) {
  let stat;
  try {
    stat = fs.lstatSync(target);
  } catch (error) {
    if (error.code === 'ENOENT') return;
    throw error;
  }
  if (stat.isDirectory() && !stat.isSymbolicLink()) fs.rmSync(target, { recursive: true });
  else fs.unlinkSync(target);
}

function detachCurrent(target, current, backup) {
  if (!current) return { target, current: null, backup: null };
  if (current.type === 'file') {
    fs.copyFileSync(target, backup);
    fs.unlinkSync(target);
  } else if (current.type === 'directory') {
    fs.renameSync(target, backup);
  } else {
    fs.unlinkSync(target);
  }
  return { target, current, backup: current.type === 'symlink' ? null : backup };
}

function restoreBefore(operation) {
  const target = operation.target;
  if (!operation.before) return;
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o755 });
  if (operation.before.type === 'file') {
    const bytes = fs.readFileSync(operation.backupAbsolute);
    if (sha256(bytes) !== operation.before.hash) throw new Error(`Rollback file backup changed: ${operation.path}.`);
    atomicWrite(target, bytes, operation.before.mode);
  } else if (operation.before.type === 'symlink') {
    fs.symlinkSync(operation.before.link_target, target);
  } else {
    const temporary = `${target}.rollback-${process.pid}-${randomBytes(5).toString('hex')}`;
    try {
      fs.cpSync(operation.backupAbsolute, temporary, {
        recursive: true,
        dereference: false,
        preserveTimestamps: true,
        verbatimSymlinks: true,
      });
      fs.chmodSync(temporary, operation.before.mode);
      const copied = inspectSetupTarget(temporary);
      if (copied.type !== 'directory' || copied.hash !== operation.before.hash || copied.mode !== operation.before.mode) {
        throw new Error(`Rollback directory backup changed: ${operation.path}.`);
      }
      fs.renameSync(temporary, target);
    } catch (error) {
      if (fs.existsSync(temporary)) fs.rmSync(temporary, { recursive: true, force: true });
      throw error;
    }
  }
  if (!sameSnapshot(inspectSetupTarget(target), operation.before)) throw new Error(`Rollback restore proof failed: ${operation.path}.`);
}

function restoreDetached(item) {
  removePath(item.target);
  if (!item.current) return;
  fs.mkdirSync(path.dirname(item.target), { recursive: true, mode: 0o755 });
  if (item.current.type === 'file') atomicWrite(item.target, fs.readFileSync(item.backup), item.current.mode);
  else if (item.current.type === 'directory') fs.renameSync(item.backup, item.target);
  else fs.symlinkSync(item.current.link_target, item.target);
}

export function applyRollbackPlan(plan, {
  home,
  now = Date.now(),
  failAfter = null,
  finalize = null,
  onRollback = null,
  transactionContext,
  crashAfter = null,
} = {}) {
  if (sha256(path.resolve(home)) !== plan.target_home_digest) throw new Error('Rollback plan belongs to another target home.');
  const manifestFile = manifestPath(home);
  const currentManifest = fs.readFileSync(manifestFile);
  if (sha256(currentManifest) !== plan.current_manifest_hash) throw new Error('Install manifest changed after rollback approval.');
  if (!transactionContext) throw new Error('Rollback requires a durable transaction context.');
  const transaction = transactionContext.directory;
  const applied = [];
  try {
    for (const [index, source] of plan.operations.entries()) {
      const target = safeSetupTarget(home, source.path);
      const current = inspectSetupTarget(target);
      if (!sameSnapshot(current, source.after)) throw new Error(`Rollback target changed after approval: ${source.path}.`);
      const backup = path.join(transaction, `${index}.current`);
      const journalIndex = transactionContext.prepare({
        path: source.path,
        before: source.after,
        after: source.before,
        backup: current && current.type !== 'symlink' ? path.basename(backup) : null,
      });
      const item = detachCurrent(target, current, backup);
      applied.push(item);
      restoreBefore({ ...source, target });
      transactionContext.applied(journalIndex);
      if (crashAfter !== null && applied.length >= crashAfter) process.kill(process.pid, 'SIGKILL');
      if (failAfter !== null && applied.length >= failAfter) throw new Error('Injected rollback failure.');
    }
    const previous = plan.receipt.previous_manifest;
    if (previous.present) {
      const bytes = fs.readFileSync(path.join(plan.bundle, previous.backup));
      if (sha256(bytes) !== previous.hash) throw new Error('Previous install manifest changed during rollback.');
      atomicWrite(manifestFile, bytes, 0o600);
    } else if (fs.existsSync(manifestFile)) {
      fs.unlinkSync(manifestFile);
    }
    const finalization = finalize ? finalize() : null;
    transactionContext.mark('committed');
    for (const operation of plan.operations.filter((item) => item.action === 'remove-created')) {
      pruneEmptyParents(safeSetupTarget(home, operation.path), home);
    }
    transactionContext.complete();
    return {
      status: 'PASS',
      mode: 'rollback',
      plan_digest: plan.plan_digest,
      rollback_bundle: plan.backup_bundle_id,
      changed: applied.length,
      ...(finalization ? { finalization } : {}),
      restored_at: new Date(now).toISOString(),
    };
  } catch (error) {
    for (const item of [...applied].reverse()) restoreDetached(item);
    atomicWrite(manifestFile, currentManifest, 0o600);
    if (onRollback) {
      try {
        onRollback();
      } catch (recoveryError) {
        throw new AggregateError(
          [error, recoveryError],
          'Rollback failed and external plugin reconciliation also failed.',
        );
      }
    }
    transactionContext.abort();
    throw error;
  }
}
