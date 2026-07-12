export const INSTALL_MANIFEST_SCHEMA = 'hard-eng/install-manifest/v1';

const manifestKeys = new Set([
  'schema', 'status', 'version', 'source_digest', 'target_home_digest', 'entries',
  'rollback_bundle', 'updated_at', 'migration',
]);
const entryKeys = new Set([
  'path', 'expected_type', 'source_hash', 'installed_hash',
  'previous_target_hash', 'rollback_action', 'mode',
]);

function plain(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function keys(value, allowed, label) {
  if (!plain(value)) throw new Error(`${label} must be an object.`);
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
}

function digest(value, label) {
  if (!/^[a-f0-9]{64}$/.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function safeRelative(value) {
  return typeof value === 'string'
    && value.length > 0
    && value.length <= 500
    && !value.startsWith('/')
    && !value.includes('\\')
    && value.split('/').every((part) => part && part !== '.' && part !== '..');
}

export function validateInstallManifest(value) {
  keys(value, manifestKeys, 'Install manifest');
  if (value.schema !== INSTALL_MANIFEST_SCHEMA) throw new Error('Install manifest schema is invalid.');
  if (!['installed', 'uninstalled'].includes(value.status)) throw new Error('Install manifest status is invalid.');
  if (typeof value.version !== 'string' || !value.version || value.version.length > 80 || /[\r\n\0]/.test(value.version)) {
    throw new Error('Install manifest version is invalid.');
  }
  digest(value.source_digest, 'Install manifest source digest');
  digest(value.target_home_digest, 'Install manifest target-home digest');
  if (!Array.isArray(value.entries) || value.entries.length > 10_000) throw new Error('Install manifest entry ledger is invalid.');
  if (value.status === 'uninstalled' && value.entries.length !== 0) throw new Error('Uninstalled manifest cannot own files.');
  const paths = new Set();
  for (const entry of value.entries) {
    keys(entry, entryKeys, 'Install manifest entry');
    if (!safeRelative(entry.path) || paths.has(entry.path)) throw new Error('Install manifest entry path is invalid or duplicated.');
    paths.add(entry.path);
    if (!['file', 'symlink'].includes(entry.expected_type)) throw new Error('Install manifest entry type is invalid.');
    digest(entry.source_hash, 'Install manifest source hash');
    digest(entry.installed_hash, 'Install manifest installed hash');
    if (entry.source_hash !== entry.installed_hash) throw new Error('Install manifest source and installed hashes differ.');
    if (entry.previous_target_hash !== null) digest(entry.previous_target_hash, 'Install manifest previous-target hash');
    if (!['remove', 'restore-backup'].includes(entry.rollback_action)) throw new Error('Install manifest rollback action is invalid.');
    if (entry.expected_type === 'symlink') {
      if (entry.mode !== null) throw new Error('Install manifest symlink mode is invalid.');
    } else if (!Number.isInteger(entry.mode) || entry.mode < 0 || entry.mode > 0o777) {
      throw new Error('Install manifest file mode is invalid.');
    }
  }
  if (value.rollback_bundle !== null) {
    keys(value.rollback_bundle, new Set(['bundle_id', 'source_plan_digest', 'receipt_digest']), 'Install manifest rollback bundle');
    digest(value.rollback_bundle.bundle_id, 'Install manifest rollback bundle ID');
    digest(value.rollback_bundle.source_plan_digest, 'Install manifest rollback source-plan digest');
    digest(value.rollback_bundle.receipt_digest, 'Install manifest rollback receipt digest');
  }
  if (!Number.isFinite(Date.parse(value.updated_at))) throw new Error('Install manifest update timestamp is invalid.');
  if (value.migration !== undefined && (!Array.isArray(value.migration) || value.migration.length !== 0)) {
    throw new Error('Install manifest migration residue is invalid.');
  }
  return true;
}
