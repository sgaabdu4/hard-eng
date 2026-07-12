import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson, digestValue, sha256 } from './canonical.mjs';
import {
  assertExactObject,
  assertSha256Digest,
  sameSetupSnapshot,
  validateSetupSnapshot,
} from './setup-schema.mjs';
import {
  ROLLBACK_BUNDLE_SCHEMA,
  atomicWrite,
  inspectSetupTarget,
  manifestPath,
  mkdirPrivate,
  rollbackBundlePath,
  safeSetupTarget,
} from './setup-transaction.mjs';

const JOURNAL_SCHEMA = 'hard-eng/setup-journal/v1';
const RECOVERY_PLAN_SCHEMA = 'hard-eng/setup-recovery-plan/v1';
const journalKeys = [
  'schema', 'transaction_id', 'pid', 'plan_digest', 'target_home_digest',
  'previous_codex_mcp_status', 'previous_manifest', 'rollback_bundle_id',
  'status', 'entries', 'created_at', 'updated_at',
];
const journalEntryKeys = ['path', 'before', 'after', 'backup', 'status'];
const backupPattern = /^(?:\d+\.(?:backup|current)|cutover-(?:config\.(?:before|removed)|cache\.before))$/;

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

export function beginSetupTransaction({
  home,
  plan,
  previousManifest,
  previousCodexMcpConfigured,
  previousCodexMcpStatus = previousCodexMcpConfigured ? 'PASS' : 'NOT_CONFIGURED',
  now = Date.now(),
}) {
  if (!['PASS', 'NOT_CONFIGURED', 'MIGRATION_REQUIRED'].includes(previousCodexMcpStatus)) {
    throw new Error('Previous Codex MCP status is invalid.');
  }
  const previousManifestHash = previousManifest ? sha256(previousManifest) : null;
  if (
    (Object.hasOwn(plan, 'existing_manifest_hash') && plan.existing_manifest_hash !== previousManifestHash)
    || (Object.hasOwn(plan, 'current_manifest_hash') && plan.current_manifest_hash !== previousManifestHash)
  ) throw new Error('Install manifest changed after setup approval.');
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
        previous_codex_mcp_status: previousCodexMcpStatus,
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

function processAlive(pid) {
  if (!Number.isInteger(pid) || pid < 1) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

function assertIsoTimestamp(value, label) {
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) {
    throw new Error(`${label} timestamp is invalid.`);
  }
}

function validatePreviousManifest(directory, value) {
  assertExactObject(value, ['present', 'hash', 'backup'], 'Setup recovery previous manifest');
  if (typeof value.present !== 'boolean') throw new Error('Setup recovery previous-manifest presence is invalid.');
  if (!value.present) {
    if (value.hash !== null || value.backup !== null) {
      throw new Error('Setup recovery absent previous-manifest metadata is invalid.');
    }
    return;
  }
  assertSha256Digest(value.hash, 'Setup recovery previous-manifest hash');
  if (value.backup !== 'previous-manifest.json') {
    throw new Error('Setup recovery previous-manifest backup is invalid.');
  }
  const backup = path.join(directory, value.backup);
  const stat = fs.lstatSync(backup);
  if (
    !stat.isFile()
    || stat.isSymbolicLink()
    || stat.size > 4 * 1024 * 1024
    || sha256(fs.readFileSync(backup)) !== value.hash
  ) throw new Error('Setup recovery previous manifest is stale or corrupt.');
}

function validateJournalEntry(home, entry, index) {
  const label = `Setup recovery journal entry ${index}`;
  assertExactObject(entry, journalEntryKeys, label);
  safeSetupTarget(home, entry.path);
  validateSetupSnapshot(entry.before, `${label} before snapshot`);
  validateSetupSnapshot(entry.after, `${label} after snapshot`);
  if (entry.before === null && entry.after === null) throw new Error(`${label} has no state transition.`);
  if (!['prepared', 'applied'].includes(entry.status)) throw new Error(`${label} status is invalid.`);
  if (!entry.before || entry.before.type === 'symlink') {
    if (entry.backup !== null) throw new Error(`${label} backup is unexpected.`);
  } else if (!backupPattern.test(entry.backup ?? '')) {
    throw new Error(`${label} backup path is invalid.`);
  }
}

function readJournal(directory, home) {
  const directoryStat = fs.lstatSync(directory);
  if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink()) {
    throw new Error('Setup recovery transaction directory is unsafe.');
  }
  const file = path.join(directory, 'journal.json');
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 4 * 1024 * 1024) throw new Error('Setup recovery journal is unsafe.');
  const journal = JSON.parse(fs.readFileSync(file, 'utf8'));
  assertExactObject(journal, journalKeys, 'Setup recovery journal');
  if (journal.schema !== JOURNAL_SCHEMA) throw new Error('Setup recovery journal schema is invalid.');
  const transactionMatch = /^transaction-([1-9][0-9]*)-([a-f0-9]{16})$/.exec(journal.transaction_id ?? '');
  if (
    !transactionMatch
    || journal.transaction_id !== path.basename(directory)
    || !Number.isSafeInteger(journal.pid)
    || journal.pid < 1
    || Number(transactionMatch[1]) !== journal.pid
  ) throw new Error('Setup recovery transaction identity is invalid.');
  assertSha256Digest(journal.plan_digest, 'Setup recovery plan digest');
  assertSha256Digest(journal.target_home_digest, 'Setup recovery target-home digest');
  if (!['PASS', 'NOT_CONFIGURED', 'MIGRATION_REQUIRED'].includes(journal.previous_codex_mcp_status)) {
    throw new Error('Setup recovery previous Codex MCP status is invalid.');
  }
  validatePreviousManifest(directory, journal.previous_manifest);
  if (journal.rollback_bundle_id !== null) {
    assertSha256Digest(journal.rollback_bundle_id, 'Setup recovery rollback-bundle ID');
  }
  if (!['applying', 'files-applied', 'external-applied', 'committed'].includes(journal.status)) {
    throw new Error('Setup recovery journal status is invalid.');
  }
  assertIsoTimestamp(journal.created_at, 'Setup recovery created-at');
  assertIsoTimestamp(journal.updated_at, 'Setup recovery updated-at');
  if (!Array.isArray(journal.entries) || journal.entries.length > 10_000) {
    throw new Error('Setup recovery journal entry ledger is invalid.');
  }
  journal.entries.forEach((entry, index) => validateJournalEntry(home, entry, index));
  if (
    ['external-applied', 'committed'].includes(journal.status)
    && journal.entries.some((entry) => entry.status !== 'applied')
  ) throw new Error('Setup recovery completed journal contains a prepared entry.');
  return { file, journal };
}

function verifyBackup(directory, entry) {
  if (!entry.before || entry.before.type === 'symlink') return null;
  if (!backupPattern.test(entry.backup ?? '')) {
    throw new Error('Setup recovery backup path is invalid.');
  }
  const backup = path.join(directory, entry.backup);
  const observed = inspectSetupTarget(backup);
  if (!sameSetupSnapshot(observed, entry.before)) throw new Error(`Setup recovery backup is stale: ${entry.path}.`);
  return backup;
}

function verifyRollbackBundleIdentity(home, journal) {
  if (!journal.rollback_bundle_id) return;
  const bundle = rollbackBundlePath(home, journal.rollback_bundle_id);
  if (!fs.existsSync(bundle)) return;
  const bundleStat = fs.lstatSync(bundle);
  if (!bundleStat.isDirectory() || bundleStat.isSymbolicLink()) {
    throw new Error('Recovery rollback bundle root is unsafe.');
  }
  const receiptFile = path.join(bundle, 'receipt.json');
  const receiptStat = fs.lstatSync(receiptFile);
  if (!receiptStat.isFile() || receiptStat.isSymbolicLink() || receiptStat.size > 4 * 1024 * 1024) {
    throw new Error('Recovery rollback bundle receipt is unsafe.');
  }
  const receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf8'));
  if (
    receipt?.schema !== ROLLBACK_BUNDLE_SCHEMA
    || receipt.bundle_id !== journal.rollback_bundle_id
    || receipt.source_plan_digest !== journal.plan_digest
  ) throw new Error('Recovery rollback bundle identity is invalid.');
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

export function buildSetupRecoveryPlan({ home, isProcessAlive = processAlive }) {
  const directories = transactionDirectories(home);
  if (directories.length !== 1) throw new Error('Recovery requires exactly one incomplete setup transaction.');
  const directory = directories[0];
  const { journal } = readJournal(directory, home);
  if (sha256(path.resolve(home)) !== journal.target_home_digest) throw new Error('Recovery journal belongs to another home.');
  if (isProcessAlive(journal.pid)) throw new Error('The setup transaction process is still running.');
  const virtual = new Map();
  const operations = [...journal.entries].reverse().map((entry) => {
    const target = safeSetupTarget(home, entry.path);
    const current = virtual.has(entry.path) ? virtual.get(entry.path) : inspectSetupTarget(target);
    if (sameSetupSnapshot(current, entry.before)) {
      virtual.set(entry.path, entry.before);
      return { ...entry, action: 'noop', backup: null };
    }
    const backup = verifyBackup(directory, entry);
    if (!sameSetupSnapshot(current, entry.after)) throw new Error(`Recovery target drifted: ${entry.path}.`);
    virtual.set(entry.path, entry.before);
    return { ...entry, action: entry.before ? `restore-${entry.before.type}` : 'remove-created', backup };
  }).reverse();
  verifyRollbackBundleIdentity(home, journal);
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
    previous_codex_mcp_status: journal.previous_codex_mcp_status,
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
  if (!sameSetupSnapshot(inspectSetupTarget(target), entry.before)) throw new Error(`Recovery restore proof failed: ${entry.path}.`);
}

export function applySetupRecoveryPlan(plan, { home, wiringClient, isProcessAlive = processAlive }) {
  if (sha256(path.resolve(home)) !== plan.target_home_digest) throw new Error('Recovery plan belongs to another home.');
  const current = buildSetupRecoveryPlan({ home, isProcessAlive });
  if (current.plan_digest !== plan.plan_digest) throw new Error('Recovery journal changed after approval.');
  const { journal } = current;
  for (const entry of [...current.operations].reverse()) restoreEntry(home, entry);
  const manifest = manifestPath(home);
  if (journal.previous_manifest.present) {
    const backup = path.join(current.directory, journal.previous_manifest.backup);
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
  let wiring;
  if (journal.previous_codex_mcp_status === 'MIGRATION_REQUIRED') {
    const observed = wiringClient.inspect(home);
    if (observed.status !== 'MIGRATION_REQUIRED') throw new Error('Recovery did not restore the installed Codex owner.');
    wiring = {
      status: 'PASS', action: 'verify-restored', changed: false,
      evidence_digest: observed.evidence_digest,
    };
  } else {
    wiring = wiringClient.reconcile(home, journal.previous_codex_mcp_status === 'PASS');
  }
  fs.rmSync(current.directory, { recursive: true });
  releaseLock(lockPath(home));
  return {
    status: 'PASS',
    mode: 'recover',
    plan_digest: current.plan_digest,
    restored: current.operations.filter((entry) => entry.action !== 'noop').length,
    codex_mcp: wiring,
  };
}
