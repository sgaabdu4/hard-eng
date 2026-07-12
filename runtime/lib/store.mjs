import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { canonicalJson } from './canonical.mjs';
import { identityHash, randomKey } from './crypto.mjs';
import { resolveGitIdentity } from './git.mjs';
import { validateRun, validateSession } from './schema.mjs';

function mkdirPrivate(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  fs.chmodSync(directory, 0o700);
}

function syncDirectory(directory) {
  let fd;
  try {
    fd = fs.openSync(directory, 'r');
    fs.fsyncSync(fd);
  } catch (error) {
    if (!['EINVAL', 'ENOTSUP', 'EISDIR', 'EPERM'].includes(error.code)) throw error;
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}

function writePrivateFileExclusive(file, data) {
  const fd = fs.openSync(file, 'wx', 0o600);
  try {
    fs.writeFileSync(fd, data);
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  fs.chmodSync(file, 0o600);
  syncDirectory(path.dirname(file));
}

export function resolveStore(cwd, options = {}) {
  const identity = resolveGitIdentity(cwd);
  const root = path.join(identity.commonDir, 'common', 'hard-eng', 'v1');
  const store = {
    ...identity,
    root,
    runsDir: path.join(root, 'runs'),
    sessionsDir: path.join(root, 'sessions'),
    locksDir: path.join(root, 'locks'),
    keysDir: path.join(root, 'keys'),
    keyPath: path.join(root, 'keys', 'session-hmac.key'),
    exists: fs.existsSync(root),
  };
  return options.create ? initializeStore(store) : store;
}

function initializeStore(store) {
  for (const directory of [store.root, store.runsDir, store.sessionsDir, store.locksDir, store.keysDir]) {
    mkdirPrivate(directory);
  }
  if (!fs.existsSync(store.keyPath)) {
    try {
      writePrivateFileExclusive(store.keyPath, randomKey());
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
  }
  fs.chmodSync(store.keyPath, 0o600);
  return { ...store, exists: true };
}

export function ensureStore(cwd) {
  return resolveStore(cwd, { create: true });
}

export function storeFromRoot(root) {
  const normalized = path.resolve(root);
  const suffix = path.join('common', 'hard-eng', 'v1');
  if (!normalized.endsWith(suffix)) throw new Error('Envelope store root is invalid.');
  const commonDir = normalized.slice(0, -(suffix.length + 1));
  const realCommon = fs.realpathSync(commonDir);
  return {
    commonDir: realCommon,
    repoId: identityHash(`git-common\0${realCommon}`),
    checkoutId: null,
    checkoutRoot: null,
    gitDir: null,
    root: normalized,
    runsDir: path.join(normalized, 'runs'),
    sessionsDir: path.join(normalized, 'sessions'),
    locksDir: path.join(normalized, 'locks'),
    keysDir: path.join(normalized, 'keys'),
    keyPath: path.join(normalized, 'keys', 'session-hmac.key'),
    exists: fs.existsSync(normalized),
  };
}

export function readKey(store) {
  const key = fs.readFileSync(store.keyPath);
  if (key.length !== 32) throw new Error('Hard Eng session key is invalid.');
  return key;
}

function atomicWriteJson(file, value, validator) {
  validator(value);
  const body = `${canonicalJson(value)}\n`;
  const temporary = `${file}.tmp-${process.pid}-${randomBytes(6).toString('hex')}`;
  let fd;
  try {
    fd = fs.openSync(temporary, 'wx', 0o600);
    fs.writeFileSync(fd, body);
    fs.fsyncSync(fd);
    fs.closeSync(fd);
    fd = undefined;
    fs.renameSync(temporary, file);
    fs.chmodSync(file, 0o600);
    syncDirectory(path.dirname(file));
  } catch (error) {
    if (fd !== undefined) fs.closeSync(fd);
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    throw error;
  }
}

function safeName(value, label) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(value ?? '')) throw new Error(`${label} is invalid.`);
  return value;
}

function runPath(store, runId) {
  return path.join(store.runsDir, `${safeName(runId, 'Run ID')}.json`);
}

export function withLock(store, lockId, metadata, callback) {
  safeName(lockId, 'Lock ID');
  const file = path.join(store.locksDir, `${lockId}.lock`);
  const token = randomBytes(16).toString('hex');
  try {
    writePrivateFileExclusive(file, `${canonicalJson({ ...metadata, pid: process.pid, token })}\n`);
  } catch (error) {
    if (error.code === 'EEXIST') throw new Error(`Hard Eng state is locked: ${lockId}.`);
    throw error;
  }
  try {
    return callback();
  } finally {
    let current = null;
    try {
      current = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
      current = null;
    }
    if (current?.token === token) fs.unlinkSync(file);
  }
}

export function readLock(store, lockId) {
  const file = path.join(store.locksDir, `${safeName(lockId, 'Lock ID')}.lock`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function listLocks(store) {
  if (!fs.existsSync(store.locksDir)) return [];
  return fs.readdirSync(store.locksDir)
    .filter((name) => name.endsWith('.lock'))
    .sort()
    .map((name) => {
      const value = JSON.parse(fs.readFileSync(path.join(store.locksDir, name), 'utf8'));
      const { token: ignored, ...safe } = value;
      return { id: name.slice(0, -5), ...safe };
    });
}

export function createRun(store, run) {
  return withLock(store, run.run_id, { owner: run.lease.task_hash, action: 'create', time: run.updated_at }, () => {
    const file = runPath(store, run.run_id);
    if (fs.existsSync(file)) throw new Error(`Run already exists: ${run.run_id}.`);
    atomicWriteJson(file, run, validateRun);
    return run;
  });
}

export function readRun(store, runId) {
  const file = runPath(store, runId);
  if (!fs.existsSync(file)) return null;
  const run = JSON.parse(fs.readFileSync(file, 'utf8'));
  validateRun(run);
  return run;
}

export function updateRun(store, runId, expectedRevision, updater) {
  return withLock(store, runId, { owner: 'cas', action: 'update', time: new Date().toISOString() }, () => {
    const current = readRun(store, runId);
    if (!current) throw new Error(`Run not found: ${runId}.`);
    if (current.revision !== expectedRevision) {
      throw new Error(`Run revision mismatch: expected ${expectedRevision}, found ${current.revision}.`);
    }
    const next = updater(structuredClone(current));
    const changed = { ...next, revision: current.revision + 1 };
    atomicWriteJson(runPath(store, runId), changed, validateRun);
    return changed;
  });
}

export function listRuns(store) {
  if (!fs.existsSync(store.runsDir)) return [];
  return fs.readdirSync(store.runsDir)
    .filter((name) => name.endsWith('.json'))
    .map((name) => readRun(store, name.slice(0, -5)))
    .sort((left, right) => left.run_id.localeCompare(right.run_id));
}

function sessionPath(store, taskHash) {
  if (!/^[a-f0-9]{64}$/i.test(taskHash ?? '')) throw new Error('Task hash is invalid.');
  return path.join(store.sessionsDir, `${taskHash}.json`);
}

export function readSession(store, taskHash) {
  const file = sessionPath(store, taskHash);
  if (!fs.existsSync(file)) return null;
  const session = JSON.parse(fs.readFileSync(file, 'utf8'));
  validateSession(session);
  return session;
}

export function writeSession(store, session) {
  atomicWriteJson(sessionPath(store, session.task_hash), session, validateSession);
  return session;
}

export function listSessions(store) {
  if (!fs.existsSync(store.sessionsDir)) return [];
  return fs.readdirSync(store.sessionsDir)
    .filter((name) => /^[a-f0-9]{64}\.json$/i.test(name))
    .sort()
    .map((name) => readSession(store, name.slice(0, -5)));
}
