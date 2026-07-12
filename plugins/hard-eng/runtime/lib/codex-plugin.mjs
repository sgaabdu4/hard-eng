import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { sha256 } from './canonical.mjs';
import { redactErrorMessage } from './redact.mjs';

export const CORE_PLUGIN_ID = 'hard-eng@personal';
const optionalPluginNames = new Set([
  'hard-eng-flutter',
  'hard-eng-appwrite',
  'hard-eng-web',
  'hard-eng-sentry',
  'hard-eng-delivery',
  'hard-eng-authoring',
]);

function childEnvironment(home, env) {
  const output = { HOME: path.resolve(home), NO_COLOR: '1' };
  for (const key of [
    'PATH', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM',
  ]) {
    if (env[key] !== undefined) output[key] = env[key];
  }
  return output;
}

function defaultRun(args, { home, env }) {
  const result = spawnSync('codex', args, {
    env: childEnvironment(home, env),
    encoding: 'utf8',
    timeout: 20_000,
    maxBuffer: 512 * 1024,
    shell: false,
  });
  return {
    status: result.status,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? '',
    error: result.error ?? null,
  };
}

function runChecked(run, args, options, label) {
  const result = run(args, options);
  const evidenceDigest = sha256(`${result.stdout ?? ''}\0${result.stderr ?? ''}`);
  if (result.error || result.status !== 0) {
    const detail = redactErrorMessage(result.error?.message ?? result.stderr ?? result.stdout ?? 'unknown failure');
    throw new Error(`${label} failed (${evidenceDigest.slice(0, 12)}): ${detail}`);
  }
  return { ...result, evidenceDigest };
}

function runJson(run, args, options, label) {
  const result = runChecked(run, args, options, label);
  try {
    return { value: JSON.parse(result.stdout), evidenceDigest: result.evidenceDigest };
  } catch {
    throw new Error(`${label} returned invalid JSON (${result.evidenceDigest.slice(0, 12)}).`);
  }
}

function samePath(left, right) {
  try {
    return fs.realpathSync(left) === fs.realpathSync(right);
  } catch {
    return path.resolve(left) === path.resolve(right);
  }
}

function expectedVersion(home) {
  const file = path.join(home, '.agents', 'plugins', 'hard-eng', '.codex-plugin', 'plugin.json');
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8')).version ?? null;
}

function inventoryFrom(value, home) {
  const installed = Array.isArray(value?.installed) ? value.installed : [];
  const available = Array.isArray(value?.available) ? value.available : [];
  const all = [...installed, ...available];
  const core = all.find((entry) => entry.pluginId === CORE_PLUGIN_ID) ?? null;
  const conflicts = all.filter((entry) => entry.name === 'hard-eng' && entry.pluginId !== CORE_PLUGIN_ID);
  const expectedSource = path.join(home, '.agents', 'plugins', 'hard-eng');
  const version = expectedVersion(home);
  const optional = all.filter((entry) => optionalPluginNames.has(entry.name));
  return {
    core,
    conflicts,
    expectedSource,
    expectedVersion: version,
    optional,
    coreInstalled: core?.installed === true,
    coreEnabled: core?.enabled === true,
    sourceMatches: Boolean(core?.source?.path) && samePath(core.source.path, expectedSource),
    versionMatches: Boolean(version) && core?.version === version,
    optionalComplete: optionalPluginNames.size === new Set(optional.map((entry) => entry.name)).size,
    optionalDisabled: optional.every((entry) => entry.installed === false && entry.enabled === false),
  };
}

export function createCodexPluginClient({ env = process.env, run = defaultRun } = {}) {
  function readInventory(home) {
    const list = runJson(run, ['plugin', 'list', '--available', '--json'], { home, env }, 'Codex plugin inventory');
    const features = runChecked(run, ['features', 'list'], { home, env }, 'Codex feature inventory');
    const inventory = inventoryFrom(list.value, home);
    const hooksFeature = /^hooks\s+\S+\s+true\s*$/m.test(features.stdout);
    return {
      ...inventory,
      hooksFeature,
      evidenceDigest: sha256(`${list.evidenceDigest}\0${features.evidenceDigest}`),
    };
  }

  function inspect(home) {
    try {
      const value = readInventory(home);
      const pass = value.conflicts.length === 0
        && value.coreInstalled
        && value.coreEnabled
        && value.sourceMatches
        && value.versionMatches
        && value.optionalComplete
        && value.optionalDisabled
        && value.hooksFeature;
      return {
        status: pass ? 'PASS' : 'FAIL',
        core: {
          installed: value.coreInstalled,
          enabled: value.coreEnabled,
          source_matches: value.sourceMatches,
          version_matches: value.versionMatches,
          version: value.core?.version ?? null,
        },
        optional_packs: {
          discovered: value.optional.length,
          expected: optionalPluginNames.size,
          disabled: value.optionalDisabled,
        },
        hooks_feature: value.hooksFeature,
        conflicting_owners: value.conflicts.length,
        evidence_digest: value.evidenceDigest,
      };
    } catch (error) {
      return {
        status: 'FAIL',
        reason: redactErrorMessage(error.message),
        evidence_digest: sha256(error.message),
      };
    }
  }

  function reconcile(home, desiredInstalled) {
    const before = readInventory(home);
    if (before.conflicts.length > 0) throw new Error('Another hard-eng plugin owner is present; choose one owner before setup.');
    const action = desiredInstalled ? 'add' : 'remove';
    const shouldRun = desiredInstalled || before.coreInstalled;
    let actionDigest = sha256('not-run');
    if (shouldRun) {
      const result = runJson(
        run,
        ['plugin', action, CORE_PLUGIN_ID, '--json'],
        { home, env },
        `Codex plugin ${action}`,
      );
      actionDigest = result.evidenceDigest;
    }
    const after = readInventory(home);
    const correct = desiredInstalled
      ? after.coreInstalled && after.coreEnabled && after.sourceMatches && after.versionMatches
        && after.optionalComplete && after.optionalDisabled && after.hooksFeature
      : !after.coreInstalled && !after.coreEnabled;
    if (!correct) throw new Error(`Codex plugin ${action} did not reach the approved state.`);
    return {
      status: 'PASS',
      action,
      changed: desiredInstalled ? !before.coreInstalled || !before.versionMatches : before.coreInstalled,
      evidence_digest: sha256(`${before.evidenceDigest}\0${actionDigest}\0${after.evidenceDigest}`),
    };
  }

  return { inspect, reconcile };
}
