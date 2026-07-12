import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';
import { safeSetupTarget } from './setup-transaction.mjs';

const managedBins = [
  'codex-cleanup',
  'codex-context-mode-health',
  'codex-health',
  'codex-update-stack',
  'codex-watchdog',
];
const launchAgentPath = 'Library/LaunchAgents/dev.hard-eng.codex-watchdog.plist';
const cronOwner = /(?:\.agents\/scripts\/auto-sync\.sh|\.codex\/bin\/codex-(?:watchdog|update-stack|health|cleanup)|dev\.hard-eng)/i;

function pathType(home, relative) {
  const target = safeSetupTarget(home, relative);
  try {
    const stat = fs.lstatSync(target);
    if (stat.isSymbolicLink()) return 'symlink';
    if (stat.isFile()) return 'file';
    if (stat.isDirectory()) return 'directory';
    return 'unsupported';
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function boundedFile(home, relative, maxBytes) {
  const target = safeSetupTarget(home, relative);
  const stat = fs.lstatSync(target);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > maxBytes) return null;
  const bytes = fs.readFileSync(target);
  return { bytes, hash: sha256(bytes) };
}

function addBlocker(blockers, code, summary) {
  if (!blockers.some((item) => item.code === code)) blockers.push({ code, summary });
}

export function readCronTextForHome(home, env = process.env) {
  if (!env.HOME || path.resolve(home) !== path.resolve(env.HOME)) return null;
  const childEnv = Object.fromEntries(
    ['PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE']
      .filter((key) => env[key] !== undefined)
      .map((key) => [key, env[key]]),
  );
  const result = spawnSync('crontab', ['-l'], {
    env: childEnv,
    encoding: 'utf8',
    timeout: 5_000,
    maxBuffer: 256 * 1024,
    shell: false,
  });
  if (result.error?.code === 'ENOENT') return null;
  if (result.status === 0) return result.stdout ?? '';
  if (result.status === 1 && /no crontab/i.test(result.stderr ?? '')) return '';
  throw new Error('Current crontab could not be inventoried safely.');
}

export function inspectLegacyControlPlane(home, {
  cronText = undefined,
  env = process.env,
} = {}) {
  const blockers = [];
  const binEntries = [];
  let ownedBins = 0;
  let modifiedBins = 0;
  for (const name of managedBins) {
    const relative = `.codex/bin/${name}`;
    const type = pathType(home, relative);
    if (!type) continue;
    const file = type === 'file' ? boundedFile(home, relative, 1024 * 1024) : null;
    const owned = file?.bytes.subarray(0, 4096).toString('utf8').includes('# Managed by hard-eng installer.') === true;
    if (owned) ownedBins += 1;
    else modifiedBins += 1;
    binEntries.push({ path: relative, type, classification: owned ? 'owned' : 'modified', hash: file?.hash ?? null });
  }
  if (ownedBins > 0) {
    addBlocker(blockers, 'LEGACY_MANAGED_BIN_PRESENT', 'A Hard Eng-managed Codex binary remains active and must be retired before cutover.');
  }
  if (modifiedBins > 0) {
    addBlocker(blockers, 'MODIFIED_LEGACY_SURFACE', 'A legacy runtime path is modified or has an unexpected type and was preserved.');
  }

  const launchType = pathType(home, launchAgentPath);
  let launchAgent = { status: 'ABSENT', type: null, hash: null };
  if (launchType) {
    const file = launchType === 'file' ? boundedFile(home, launchAgentPath, 128 * 1024) : null;
    const text = file?.bytes.toString('utf8') ?? '';
    const owned = text.includes('<string>dev.hard-eng.codex-watchdog</string>')
      && text.includes('/.codex/bin/codex-watchdog</string>');
    launchAgent = {
      status: owned ? 'OWNED_BLOCKER' : 'MODIFIED_BLOCKER',
      type: launchType,
      hash: file?.hash ?? null,
    };
    addBlocker(
      blockers,
      owned ? 'LAUNCH_AGENT_REQUIRES_NATIVE_RETIREMENT' : 'MODIFIED_LEGACY_SURFACE',
      owned
        ? 'The legacy Hard Eng LaunchAgent must be retired through launchctl before cutover.'
        : 'A legacy runtime path is modified or has an unexpected type and was preserved.',
    );
  }

  const observedCron = cronText === undefined ? readCronTextForHome(home, env) : cronText;
  const matchingCron = typeof observedCron === 'string'
    ? observedCron.split(/\r?\n/).filter((line) => {
        const value = line.trim();
        return value && !value.startsWith('#') && cronOwner.test(value);
      })
    : [];
  const crontab = {
    status: typeof observedCron !== 'string' ? 'UNKNOWN' : matchingCron.length > 0 ? 'BLOCKED' : 'PASS',
    matching_entries: matchingCron.length,
    evidence_digest: sha256(typeof observedCron === 'string' ? matchingCron.join('\n') : 'unavailable'),
  };
  if (crontab.status === 'UNKNOWN') {
    addBlocker(blockers, 'CRONTAB_INVENTORY_UNAVAILABLE', 'The selected home crontab could not be proven free of Hard Eng jobs.');
  } else if (crontab.status === 'BLOCKED') {
    addBlocker(blockers, 'CRONTAB_REQUIRES_NATIVE_RETIREMENT', 'Legacy Hard Eng cron jobs must be retired through crontab before cutover.');
  }

  const treehouseBinary = pathType(home, '.local/bin/treehouse');
  const treehouseState = pathType(home, '.treehouse');
  const treehouse = {
    present: Boolean(treehouseBinary || treehouseState),
    binary_type: treehouseBinary,
    state_type: treehouseState,
  };
  if (treehouse.present) {
    addBlocker(blockers, 'TREEHOUSE_PRESENT', 'Treehouse binary or state remains and requires separately approved retirement before cutover.');
  }

  const externalNoMistakes = {
    binary_type: pathType(home, '.local/bin/no-mistakes'),
    state_type: pathType(home, '.no-mistakes'),
    preserved: true,
  };
  const core = {
    status: blockers.length > 0 ? 'BLOCKED' : 'PASS',
    managed_bins: {
      present: binEntries.length,
      owned: ownedBins,
      modified: modifiedBins,
      entries: binEntries,
    },
    launch_agent: launchAgent,
    crontab,
    treehouse,
    external_no_mistakes: externalNoMistakes,
    blockers,
  };
  return { ...core, evidence_digest: digestValue(core) };
}

export function assertLegacyControlPlaneReady(report) {
  if (report?.status !== 'PASS' || !/^[a-f0-9]{64}$/.test(report?.evidence_digest ?? '')) {
    throw new Error('Legacy control-plane retirement is unresolved; no live cutover mutation is allowed.');
  }
}
