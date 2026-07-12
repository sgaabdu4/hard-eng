import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { digestValue, sha256 } from './canonical.mjs';
import { validateRun, validateSession } from './schema.mjs';
import { buildSetupPlanCore } from './setup-transaction.mjs';

function inventory(root) {
  const values = [];
  const pending = [{ directory: root, prefix: '' }];
  while (pending.length) {
    const { directory, prefix } = pending.pop();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (values.length >= 10_000) throw new Error('State root exceeds the 10,000-entry purge inventory limit.');
      const relative = path.posix.join(prefix, entry.name);
      const target = path.join(directory, entry.name);
      const stat = fs.lstatSync(target);
      if (stat.isSymbolicLink() || (!stat.isDirectory() && !stat.isFile())) throw new Error('State root contains an unsafe entry type.');
      if (stat.isDirectory()) {
        values.push({ path_digest: sha256(relative), type: 'directory' });
        pending.push({ directory: target, prefix: relative });
      } else {
        if (stat.size > 2 * 1024 * 1024) throw new Error('State file exceeds the 2 MiB purge inventory limit.');
        values.push({ path_digest: sha256(relative), type: 'file', size: stat.size, content_digest: sha256(fs.readFileSync(target)) });
      }
    }
  }
  return values.sort((left, right) => left.path_digest.localeCompare(right.path_digest));
}

export function describeStateRoots(roots) {
  return [...new Set(roots.map((root) => path.resolve(root)))].map((root) => {
    if (!root.endsWith(path.join('common', 'hard-eng', 'v1'))) throw new Error('--state-root must end with common/hard-eng/v1.');
    const stat = fs.lstatSync(root);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('--state-root must be a real Hard Eng state directory.');
    const entries = inventory(root);
    return {
      root,
      public: {
        root_digest: sha256(fs.realpathSync(root)),
        content_digest: digestValue(entries),
        entries: entries.length,
      },
    };
  });
}

export function attachStatePurge(plan, descriptors) {
  const publicDescriptors = descriptors.map((item) => item.public);
  const core = buildSetupPlanCore(
    { ...plan, purge_state: true },
    { state_purge: publicDescriptors },
  );
  return { ...plan, ...core, plan_digest: digestValue(core), statePurge: descriptors };
}

function parseStateFiles(directory, expectedSchema, validator) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory).filter((name) => name.endsWith('.json')).sort().map((name) => {
    const file = path.join(directory, name);
    if (fs.statSync(file).size > 2 * 1024 * 1024) throw new Error('State record exceeds the 2 MiB migration limit.');
    const value = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (value.schema !== expectedSchema) throw new Error(`Unknown or future state schema: ${value.schema ?? '<missing>'}.`);
    validator(value);
    return sha256(fs.readFileSync(file));
  });
}

export function describeStateMigrations(roots) {
  return describeStateRoots(roots).map((descriptor) => {
    const runDigests = parseStateFiles(path.join(descriptor.root, 'runs'), 'hard-eng/run/v1', validateRun);
    const sessionDigests = parseStateFiles(path.join(descriptor.root, 'sessions'), 'hard-eng/session/v1', validateSession);
    const key = path.join(descriptor.root, 'keys', 'session-hmac.key');
    if (fs.existsSync(key) && fs.statSync(key).size !== 32) throw new Error('State migration key is invalid.');
    return {
      ...descriptor,
      public: {
        ...descriptor.public,
        status: 'current',
        from_schema: 'v1',
        to_schema: 'v1',
        run_count: runDigests.length,
        session_count: sessionDigests.length,
        records_digest: digestValue({ runDigests, sessionDigests }),
        backup_required: false,
      },
    };
  });
}

export function attachStateMigration(plan, descriptors) {
  const publicDescriptors = descriptors.map((item) => item.public);
  const core = buildSetupPlanCore(plan, { state_migration: publicDescriptors });
  return { ...plan, ...core, plan_digest: digestValue(core), stateMigration: descriptors };
}

export function validateStateMigrations(descriptors) {
  for (const descriptor of descriptors) {
    const latest = describeStateMigrations([descriptor.root])[0];
    if (latest.public.content_digest !== descriptor.public.content_digest) throw new Error('State root changed after approval.');
  }
  return 0;
}

export function purgeStateRoots(descriptors) {
  const moved = [];
  try {
    for (const descriptor of descriptors) {
      const latest = describeStateRoots([descriptor.root])[0];
      if (latest.public.content_digest !== descriptor.public.content_digest) throw new Error('State root changed after approval.');
      const backup = `${descriptor.root}.purge-${process.pid}-${randomBytes(5).toString('hex')}`;
      fs.renameSync(descriptor.root, backup);
      moved.push({ root: descriptor.root, backup });
    }
    for (const item of moved) fs.rmSync(item.backup, { recursive: true, force: true });
    return moved.length;
  } catch (error) {
    for (const item of [...moved].reverse()) {
      if (fs.existsSync(item.backup) && !fs.existsSync(item.root)) fs.renameSync(item.backup, item.root);
    }
    throw error;
  }
}
