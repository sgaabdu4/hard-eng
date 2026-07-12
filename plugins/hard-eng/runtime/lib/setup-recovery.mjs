import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson, digestValue, sha256 } from './canonical.mjs';
import {
  atomicWrite,
  inspectSetupTarget,
  manifestPath,
  mkdirPrivate,
  rollbackBundlePath,
  safeSetupTarget,
} from './setup-transaction.mjs';

const JOURNAL_SCHEMA = 'hard-eng/setup-journal/v1';
const RECOVERY_PLAN_SCHEMA = 'hard-eng/setup-recovery-plan/v1';

function stateRoot(home) {
  return path.dirname(manifestPath(home));
}

function lockPath(home) {
  return safeSetupTarget(home, '.agents/.hard-eng-install/setup.lock');
}

function writePrivate(file, bytes) {
  atomicWrite(file, bytes, 0o600);
}

function writeJournal(context) {
  context.journal.updated_at = new Date().toISOString();
  writePrivate(context.journalFile, Buffer.from(`${canonicalJson(context.journal)}\n`));
}

function acquireLock(home, planDigest) {
  const file = lockPath(home);
  mkdirPrivate(path.dirname(file));
  const fd = fs.openSync(file, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, `${canonicalJson({ pid: process.pid, plan_digest: planDigest, created_at: new Date().toISOString() })}\n`);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  return file;
}

function releaseLock(file) {
  try {
    fs.unlinkSync(file);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}

function transactionDirectories(home) {
  const root = stateRoot(home);
  if (!fs.existsSync(root)) return [];
  const stat = fs.lstatSync(root);
  if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('Installer state root is unsafe.');
  return fs.readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith('transaction-'))
    .map((entry) => path.join(root, entry.name))
    .sort();
}

export function beginSetupTransaction({ home, plan, previousManifest, previousPluginInstalled, now = Date.now() }) {
  if (transactionDirectories(home).length > 0) throw new Error('An incomplete setup transaction requires explicit recovery.');
  const lock = acquireLock(home, plan.plan_digest);
  const transactionId = `transaction-${process.pid}-${randomBytes(8).toString('hex')}`;
  const directory = safeSetupTarget(home, `.agents/.hard-eng-install/${transactionId}`);
  try {
    mkdirPrivate(directory);
    let previous = { present: false, hash: null, backup: null };
    if (previousManifest) {
      const backup = 'previous-manifest.json';
      writePrivate(path.join(directory, backup), previousManifest);
      previous = { present: true, hash: sha256(previousManifest), backup };
    }
    const context = {
      directory,
      lock,
      journalFile: path.join(directory, 'journal.json'),
      journal: {
        schema: JOURNAL_SCHEMA,
        transaction_id: transactionId,
        pid: process.pid,
        plan_digest: plan.plan_digest,
        target_home_digest: plan.target_home_digest,
        previous_plugin_installed: previousPluginInstalled,
        previous_manifest: previous,
        rollback_bundle_id: null,
        status: 'applying',
        entries: [],
        created_at: new Date(now).toISOString(),
        updated_at: new Date(now).toISOString(),
      },
    };
    writeJournal(context);
    context.prepare = (entry) => {
      context.journal.entries.push({ ...entry, status: 'prepared' });
      writeJournal(context);
      return context.journal.entries.length - 1;
    };
    context.applied = (index) => {
      context.journal.entries[index].status = 'applied';
      writeJournal(context);
    };
    context.bundleAllocated = (bundleId) => {
      context.journal.rollback_bundle_id = bundleId;
      writeJournal(context);
    };
    context.mark = (status) => {
      context.journal.status = status;
      writeJournal(context);
    };
    context.complete = () => {
      fs.rmSync(directory, { recursive: true });
      releaseLock(lock);
    };
    context.abort = () => {
      fs.rmSync(directory, { recursive: true, force: true });
      releaseLock(lock);
    };
    return context;
  } catch (error) {
    if (fs.existsSync(directory)) fs.rmSync(directory, { recursive: true, force: true });
    releaseLock(lock);
    throw error;
  }
}

function sameSnapshot(actual, expected) {
  if (!actual || !expected) return actual === expected;
  return actual.type === expected.type
    && actual.hash === expected.hash
    && (actual.mode ?? null) === (expected.mode ?? null)
    && (actual.link_target ?? null) === (expected.link_target ?? null);
}

function processAlive(pid) {
  if (!Number.isInteger(pid) || pid < 1) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

function readJournal(directory) {
  const file = path.join(directory, 'journal.json');
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 4 * 1024 * 1024) throw new Error('Setup recovery journal is unsafe.');
  const journal = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (journal.schema !== JOURNAL_SCHEMA || !Array.isArray(journal.entries)) throw new Error('Setup recovery journal schema is invalid.');
  return { file, journal };
}

function verifyBackup(directory, entry) {
  if (!entry.before || entry.before.type === 'symlink') return null;
  if (!/^\d+\.(?:backup|current)$/.test(entry.backup ?? '')) throw new Error('Setup recovery backup path is invalid.');
  const backup = path.join(directory, entry.backup);
  const observed = inspectSetupTarget(backup);
  if (!sameSnapshot(observed, entry.before)) throw new Error(`Setup recovery backup is stale: ${entry.path}.`);
  return backup;
}

export function inspectSetupRecovery(home) {
  try {
    const directories = transactionDirectories(home);
    if (!directories.length) return { status: 'PASS', pending: 0 };
    return {
      status: 'RECOVERY_REQUIRED',
      pending: directories.length,
      transaction_digest: digestValue(directories.map((directory) => path.basename(directory))),
      manual_action: 'Run `node scripts/setup.mjs recover --dry-run`, review the exact restore plan, then confirm its digest.',
    };
  } catch (error) {
    return { status: 'FAIL', pending: null, evidence_digest: sha256(error.message) };
  }
}

export function buildSetupRecoveryPlan({ home }) {
  const directories = transactionDirectories(home);
  if (directories.length !== 1) throw new Error('Recovery requires exactly one incomplete setup transaction.');
  const directory = directories[0];
  const { journal } = readJournal(directory);
  if (sha256(path.resolve(home)) !== journal.target_home_digest) throw new Error('Recovery journal belongs to another home.');
  if (processAlive(journal.pid)) throw new Error('The setup transaction process is still running.');
  const operations = journal.entries.map((entry) => {
    const target = safeSetupTarget(home, entry.path);
    const current = inspectSetupTarget(target);
    if (sameSnapshot(current, entry.before)) return { ...entry, action: 'noop', backup: null };
    const backup = verifyBackup(directory, entry);
    if (!sameSnapshot(current, entry.after)) throw new Error(`Recovery target drifted: ${entry.path}.`);
    return { ...entry, action: entry.before ? `restore-${entry.before.type}` : 'remove-created', backup };
  });
  if (journal.rollback_bundle_id) {
    const bundle = rollbackBundlePath(home, journal.rollback_bundle_id);
    if (fs.existsSync(bundle)) {
      const receipt = JSON.parse(fs.readFileSync(path.join(bundle, 'receipt.json'), 'utf8'));
      if (receipt.bundle_id !== journal.rollback_bundle_id || receipt.source_plan_digest !== journal.plan_digest) {
        throw new Error('Recovery rollback bundle identity is invalid.');
      }
    }
  }
  const publicOperations = operations.map((entry) => ({
    action: entry.action,
    path: entry.path,
    before_hash: entry.before?.hash ?? null,
    after_hash: entry.after?.hash ?? null,
  }));
  const core = {
    schema: RECOVERY_PLAN_SCHEMA,
    mode: 'recover',
    source_plan_digest: journal.plan_digest,
    target_home_digest: journal.target_home_digest,
    transaction_digest: sha256(journal.transaction_id),
    previous_plugin_installed: journal.previous_plugin_installed,
    operations: publicOperations,
  };
  return {
    ...core,
    plan_digest: digestValue(core),
    operations,
    directory,
    journal,
  };
}

function removeTarget(target) {
  const current = inspectSetupTarget(target);
  if (!current) return;
  if (current.type === 'directory') fs.rmSync(target, { recursive: true });
  else fs.unlinkSync(target);
}

function restoreEntry(home, entry) {
  if (entry.action === 'noop') return;
  const target = safeSetupTarget(home, entry.path);
  removeTarget(target);
  if (!entry.before) return;
  fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o755 });
  if (entry.before.type === 'file') atomicWrite(target, fs.readFileSync(entry.backup), entry.before.mode);
  else if (entry.before.type === 'symlink') fs.symlinkSync(entry.before.link_target, target);
  else fs.renameSync(entry.backup, target);
  if (!sameSnapshot(inspectSetupTarget(target), entry.before)) throw new Error(`Recovery restore proof failed: ${entry.path}.`);
}

export function applySetupRecoveryPlan(plan, { home, pluginClient }) {
  if (sha256(path.resolve(home)) !== plan.target_home_digest) throw new Error('Recovery plan belongs to another home.');
  const { journal } = readJournal(plan.directory);
  if (journal.plan_digest !== plan.source_plan_digest) throw new Error('Recovery journal changed after approval.');
  for (const entry of [...plan.operations].reverse()) restoreEntry(home, entry);
  const manifest = manifestPath(home);
  if (journal.previous_manifest.present) {
    const backup = path.join(plan.directory, journal.previous_manifest.backup);
    const bytes = fs.readFileSync(backup);
    if (sha256(bytes) !== journal.previous_manifest.hash) throw new Error('Recovery manifest backup changed.');
    atomicWrite(manifest, bytes, 0o600);
  } else if (fs.existsSync(manifest)) {
    fs.unlinkSync(manifest);
  }
  if (journal.rollback_bundle_id) {
    const bundle = rollbackBundlePath(home, journal.rollback_bundle_id);
    if (fs.existsSync(bundle)) fs.rmSync(bundle, { recursive: true });
  }
  const plugin = pluginClient.reconcile(home, journal.previous_plugin_installed);
  fs.rmSync(plan.directory, { recursive: true });
  releaseLock(lockPath(home));
  return {
    status: 'PASS',
    mode: 'recover',
    plan_digest: plan.plan_digest,
    restored: plan.operations.filter((entry) => entry.action !== 'noop').length,
    codex_plugin: plugin,
  };
}
