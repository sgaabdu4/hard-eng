import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson, sha256 } from './canonical.mjs';
import {
  INSTALL_MANIFEST_SCHEMA,
  ROLLBACK_BUNDLE_SCHEMA,
  atomicWrite,
  inspectSetupTarget,
  manifestPath,
  mkdirPrivate,
  pruneEmptyParents,
  rollbackBundlePath,
  safeSetupTarget,
} from './setup-transaction.mjs';

function fileMode(file) {
  return fs.statSync(file).mode & 0o777;
}

function snapshotView(snapshot) {
  if (!snapshot) return null;
  return {
    type: snapshot.type,
    hash: snapshot.hash,
    mode: snapshot.mode ?? null,
    ...(snapshot.link_target !== undefined ? { link_target: snapshot.link_target } : {}),
  };
}

function atomicSymlink(file, linkTarget) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o755 });
  const temporary = `${file}.tmp-${process.pid}-${randomBytes(5).toString('hex')}`;
  fs.symlinkSync(linkTarget, temporary);
  fs.renameSync(temporary, file);
}

function removeIfPresent(target) {
  try {
    const stat = fs.lstatSync(target);
    if (stat.isDirectory() && !stat.isSymbolicLink()) fs.rmSync(target, { recursive: true });
    else fs.unlinkSync(target);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}

function sourceBytes(sourceRoot, operation) {
  const bytes = operation.generated !== null
    ? Buffer.from(operation.generated)
    : fs.readFileSync(path.join(sourceRoot, operation.source_relative));
  if (sha256(bytes) !== operation.source_hash) throw new Error(`Setup source changed after approval: ${operation.path}.`);
  return bytes;
}

function writeManifest(home, manifest) {
  const file = manifestPath(home);
  mkdirPrivate(path.dirname(file));
  atomicWrite(file, Buffer.from(`${canonicalJson(manifest)}\n`), 0o600);
}

function copyBackup(source, target, type) {
  if (type === 'file') {
    fs.copyFileSync(source, target);
    fs.chmodSync(target, 0o600);
    return;
  }
  if (type === 'directory') {
    fs.cpSync(source, target, {
      recursive: true,
      dereference: false,
      preserveTimestamps: true,
      verbatimSymlinks: true,
    });
    return;
  }
  throw new Error('Only file and directory rollback data can be copied.');
}

function persistRollbackBundle({
  home, plan, applied, previousManifest, transaction, now, onBundleAllocated,
}) {
  if (!applied.length) return null;
  const bundleId = sha256(`${plan.plan_digest}\0${now}\0${randomBytes(16).toString('hex')}`);
  if (onBundleAllocated) onBundleAllocated(bundleId);
  const destination = rollbackBundlePath(home, bundleId);
  if (fs.existsSync(destination)) throw new Error('Rollback bundle already exists for this setup plan.');
  const staging = path.join(transaction, 'rollback-bundle');
  const dataRoot = path.join(staging, 'data');
  mkdirPrivate(staging);
  mkdirPrivate(dataRoot);
  const entries = applied.map((item, index) => {
    const before = snapshotView(item.before);
    let backup = null;
    if (before && ['file', 'directory'].includes(before.type)) {
      backup = `data/${index}`;
      copyBackup(item.backup, path.join(staging, backup), before.type);
      const copied = inspectSetupTarget(path.join(staging, backup));
      if (copied.type !== before.type || copied.hash !== before.hash) {
        throw new Error(`Rollback backup verification failed: ${item.operation.path}.`);
      }
    }
    return {
      path: item.operation.path,
      before,
      after: snapshotView(inspectSetupTarget(item.target)),
      backup,
    };
  });
  const previous = previousManifest
    ? { present: true, hash: sha256(previousManifest), backup: 'previous-manifest.json' }
    : { present: false, hash: null, backup: null };
  if (previousManifest) atomicWrite(path.join(staging, previous.backup), previousManifest, 0o600);
  const receipt = {
    schema: ROLLBACK_BUNDLE_SCHEMA,
    bundle_id: bundleId,
    source_mode: plan.mode,
    source_plan_digest: plan.plan_digest,
    target_home_digest: plan.target_home_digest,
    previous_manifest: previous,
    entries,
    created_at: new Date(now).toISOString(),
  };
  const receiptBytes = Buffer.from(`${canonicalJson(receipt)}\n`);
  const receiptDigest = sha256(receiptBytes);
  atomicWrite(path.join(staging, 'receipt.json'), receiptBytes, 0o600);
  mkdirPrivate(path.dirname(destination));
  fs.renameSync(staging, destination);
  fs.chmodSync(destination, 0o700);
  return {
    bundle_id: bundleId,
    source_plan_digest: plan.plan_digest,
    receipt_digest: receiptDigest,
    destination,
  };
}

function applyOperation({ home, sourceRoot, operation, transaction, transactionContext, index }) {
  const target = safeSetupTarget(home, operation.path);
  const current = inspectSetupTarget(target);
  if (
    operation.current_hash !== (current?.hash ?? null)
    || (current && operation.expected_type && current.type !== operation.expected_type)
  ) throw new Error(`Setup target changed after approval: ${operation.path}.`);
  const backup = current ? path.join(transaction, `${index}.backup`) : null;
  if (current?.type === 'file') {
    fs.copyFileSync(target, backup);
    fs.chmodSync(backup, current.mode);
  }
  const after = operation.action === 'write' ? {
    type: operation.expected_type,
    hash: operation.source_hash,
    mode: operation.expected_type === 'symlink' ? null : operation.mode,
    ...(operation.expected_type === 'symlink' ? { link_target: operation.link_target } : {}),
  } : null;
  const journalIndex = transactionContext.prepare({
    path: operation.path,
    before: snapshotView(current),
    after,
    backup: backup ? path.basename(backup) : null,
  });
  if (operation.action === 'write') {
    if (current?.type === 'directory') throw new Error(`Setup cannot replace a directory: ${operation.path}.`);
    if (operation.expected_type === 'symlink') {
      if (current) fs.unlinkSync(target);
      if (sha256(`symlink\0${operation.link_target}`) !== operation.source_hash) {
        throw new Error(`Setup symlink source changed after approval: ${operation.path}.`);
      }
      atomicSymlink(target, operation.link_target);
    } else {
      if (current?.type === 'symlink') fs.unlinkSync(target);
      atomicWrite(target, sourceBytes(sourceRoot, operation), operation.mode);
    }
  } else if (current?.type === 'directory') fs.renameSync(target, backup);
  else fs.unlinkSync(target);
  return {
    journalIndex,
    applied: {
      target,
      backup,
      existed: Boolean(current),
      type: current?.type ?? null,
      link_target: current?.link_target ?? null,
      before: snapshotView(current),
      operation,
    },
  };
}

function restoreApplied(item) {
  if (item.existed && item.type === 'file') {
    atomicWrite(item.target, fs.readFileSync(item.backup), fileMode(item.backup));
  } else if (item.existed && item.type === 'symlink') {
    removeIfPresent(item.target);
    fs.mkdirSync(path.dirname(item.target), { recursive: true });
    fs.symlinkSync(item.link_target, item.target);
  } else if (item.existed && item.type === 'directory') {
    fs.mkdirSync(path.dirname(item.target), { recursive: true });
    fs.renameSync(item.backup, item.target);
  } else {
    removeIfPresent(item.target);
  }
}

function installManifest(plan, persistedBundle, now) {
  return {
    schema: INSTALL_MANIFEST_SCHEMA,
    status: plan.mode === 'uninstall' ? 'uninstalled' : 'installed',
    version: '1.0.0',
    source_digest: plan.source_digest,
    target_home_digest: plan.target_home_digest,
    entries: plan.mode === 'uninstall' ? [] : plan.nextEntries,
    migration: plan.legacy?.filter((entry) => entry.action === 'remove') ?? [],
    rollback_bundle: persistedBundle
      ? {
          bundle_id: persistedBundle.bundle_id,
          source_plan_digest: persistedBundle.source_plan_digest,
          receipt_digest: persistedBundle.receipt_digest,
        }
      : plan.existing?.rollback_bundle ?? null,
    updated_at: new Date(now).toISOString(),
  };
}

function rollbackTransaction({
  applied, previousManifest, persistedBundle, home, onRollback, transactionContext, error,
}) {
  for (const item of [...applied].reverse()) restoreApplied(item);
  if (previousManifest) atomicWrite(manifestPath(home), previousManifest, 0o600);
  else if (fs.existsSync(manifestPath(home))) fs.unlinkSync(manifestPath(home));
  if (persistedBundle?.destination && fs.existsSync(persistedBundle.destination)) {
    fs.rmSync(persistedBundle.destination, { recursive: true, force: true });
  }
  if (onRollback) {
    try {
      onRollback();
    } catch (recoveryError) {
      throw new AggregateError(
        [error, recoveryError],
        'Setup failed and external plugin reconciliation also failed.',
      );
    }
  }
  transactionContext.abort();
}

export function applySetupPlan(plan, {
  home,
  sourceRoot,
  now = Date.now(),
  failAfter = null,
  finalize = null,
  onRollback = null,
  transactionContext,
  crashAfter = null,
} = {}) {
  if (sha256(path.resolve(home)) !== plan.target_home_digest) throw new Error('Setup plan belongs to another target home.');
  if (!transactionContext) throw new Error('Setup requires a durable transaction context.');
  const transaction = transactionContext.directory;
  const previousManifest = fs.existsSync(manifestPath(home)) ? fs.readFileSync(manifestPath(home)) : null;
  const applied = [];
  let persistedBundle = null;
  try {
    for (const operation of plan.operations) {
      if (operation.action === 'noop') continue;
      const result = applyOperation({
        home, sourceRoot, operation, transaction, transactionContext, index: applied.length,
      });
      applied.push(result.applied);
      transactionContext.applied(result.journalIndex);
      if (crashAfter !== null && applied.length >= crashAfter) process.kill(process.pid, 'SIGKILL');
      if (failAfter !== null && applied.length >= failAfter) throw new Error('Injected transaction failure.');
    }
    transactionContext.mark('files-applied');
    persistedBundle = persistRollbackBundle({
      home,
      plan,
      applied,
      previousManifest,
      transaction,
      now,
      onBundleAllocated: transactionContext.bundleAllocated,
    });
    writeManifest(home, installManifest(plan, persistedBundle, now));
    const finalization = finalize ? finalize() : null;
    transactionContext.mark('committed');
    for (const operation of plan.operations.filter((item) => item.action === 'remove')) {
      pruneEmptyParents(safeSetupTarget(home, operation.path), home);
    }
    transactionContext.complete();
    return {
      status: plan.migration_blockers?.length ? 'CONCERNS' : 'PASS',
      mode: plan.mode,
      plan_digest: plan.plan_digest,
      changed: applied.length,
      ...(finalization ? { finalization } : {}),
      ...(persistedBundle ? { rollback_bundle: persistedBundle.bundle_id } : {}),
      ...(plan.migration_blockers?.length ? { migration_blockers: plan.migration_blockers } : {}),
    };
  } catch (error) {
    rollbackTransaction({
      applied, previousManifest, persistedBundle, home, onRollback, transactionContext, error,
    });
    throw error;
  }
}
