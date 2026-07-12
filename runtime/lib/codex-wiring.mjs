import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';
import { redactErrorMessage } from './redact.mjs';

export const HARD_ENG_MCP_NAME = 'hard_eng';

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

function expectedTransport(home) {
  return {
    type: 'stdio',
    command: 'node',
    args: [path.join(path.resolve(home), '.agents', 'runtime', 'server.mjs')],
    cwd: null,
    env: {},
    env_vars: [],
  };
}

function normalizedTransport(transport) {
  if (!transport || typeof transport !== 'object') return null;
  return {
    type: transport.type ?? null,
    command: transport.command ?? null,
    args: Array.isArray(transport.args) ? transport.args : [],
    cwd: transport.cwd ?? null,
    env: transport.env && typeof transport.env === 'object' && !Array.isArray(transport.env)
      ? transport.env
      : {},
    env_vars: Array.isArray(transport.env_vars) ? transport.env_vars : [],
  };
}

function sameTransport(actual, expected) {
  return actual?.type === expected.type
    && actual.command === expected.command
    && actual.cwd === expected.cwd
    && actual.args.length === expected.args.length
    && actual.args.every((value, index) => value === expected.args[index])
    && Object.keys(actual.env).length === 0
    && actual.env_vars.length === 0;
}

function codebaseMemoryMcpFacts(entries) {
  const matches = entries
    .map((entry) => ({ entry, transport: normalizedTransport(entry.transport) }))
    .filter(({ entry, transport }) => /codebase[-_]?memory/i.test([
      entry.name, transport?.command, ...(transport?.args ?? []), transport?.cwd,
    ].filter(Boolean).join('\0')))
    .map(({ entry, transport }) => ({ name: entry.name, enabled: entry.enabled === true, transport }));
  return {
    codebase_memory_mcp_entries: matches.length,
    codebase_memory_mcp_evidence_digest: digestValue(matches),
  };
}

function isInstalledCacheTransport(home, transport) {
  if (
    transport?.type !== 'stdio'
    || transport.command !== 'node'
    || transport.args.length !== 1
    || transport.args[0] !== './runtime/server.mjs'
    || !transport.cwd
    || Object.keys(transport.env).length !== 0
    || transport.env_vars.length !== 0
  ) return false;
  const cacheRoot = path.join(path.resolve(home), '.codex', 'plugins', 'cache', 'personal', 'hard-eng');
  const relative = path.relative(cacheRoot, path.resolve(transport.cwd));
  return Boolean(relative) && !relative.startsWith('..') && !path.isAbsolute(relative) && !relative.includes(path.sep);
}

function readInventory(run, home, env) {
  const result = runJson(run, ['mcp', 'list', '--json'], { home, env }, 'Codex MCP inventory');
  if (!Array.isArray(result.value)) throw new Error('Codex MCP inventory must be an array.');
  const names = new Set();
  for (const entry of result.value) {
    if (!entry || typeof entry !== 'object' || typeof entry.name !== 'string' || !entry.name) {
      throw new Error('Codex MCP inventory contains an invalid entry.');
    }
    if (names.has(entry.name)) throw new Error(`Codex MCP inventory contains duplicate name ${entry.name}.`);
    names.add(entry.name);
  }
  const entries = [...result.value].sort((left, right) => left.name.localeCompare(right.name));
  return { entries, evidenceDigest: digestValue(entries) };
}

function classify(entries, home) {
  const supportFacts = codebaseMemoryMcpFacts(entries);
  const entry = entries.find((candidate) => candidate.name === HARD_ENG_MCP_NAME) ?? null;
  if (!entry) return { status: 'NOT_CONFIGURED', configured: false, owned: false, enabled: false, ...supportFacts };
  const transport = normalizedTransport(entry.transport);
  const owned = entry.enabled === true && sameTransport(transport, expectedTransport(home));
  const installedCacheOwner = entry.enabled === true && isInstalledCacheTransport(home, transport);
  return {
    status: owned ? 'PASS' : installedCacheOwner ? 'MIGRATION_REQUIRED' : 'CONFLICT',
    configured: true,
    owned,
    enabled: entry.enabled === true,
    transport_type: transport?.type ?? null,
    ...supportFacts,
  };
}

export function createCodexWiringClient({ env = process.env, run = defaultRun } = {}) {
  function inspect(home) {
    try {
      const inventory = readInventory(run, home, env);
      return { ...classify(inventory.entries, home), evidence_digest: inventory.evidenceDigest };
    } catch (error) {
      return {
        status: 'FAIL',
        configured: null,
        owned: null,
        codebase_memory_mcp_entries: null,
        codebase_memory_mcp_evidence_digest: sha256(error.message),
        reason: redactErrorMessage(error.message),
        evidence_digest: sha256(error.message),
      };
    }
  }

  function reconcile(home, desiredConfigured) {
    const before = readInventory(run, home, env);
    const beforeState = classify(before.entries, home);
    if (beforeState.status === 'CONFLICT') {
      throw new Error(`Unexpected ${HARD_ENG_MCP_NAME} owner blocks setup.`);
    }
    if (beforeState.status === 'MIGRATION_REQUIRED') {
      throw new Error(`The installed-cache ${HARD_ENG_MCP_NAME} owner requires an approved live cutover.`);
    }
    if (beforeState.codebase_memory_mcp_entries > 0) {
      throw new Error('Codebase Memory MCP wiring requires an approved transactional retirement.');
    }

    let action = 'none';
    let actionDigest = sha256('not-run');
    if (desiredConfigured && beforeState.status === 'NOT_CONFIGURED') {
      action = 'add';
      const transport = expectedTransport(home);
      runChecked(
        run,
        ['mcp', 'add', HARD_ENG_MCP_NAME, '--', transport.command, ...transport.args],
        { home, env },
        'Codex MCP add',
      );
      actionDigest = digestValue({ action, name: HARD_ENG_MCP_NAME, transport });
    } else if (!desiredConfigured && beforeState.status === 'PASS') {
      action = 'remove';
      runChecked(
        run,
        ['mcp', 'remove', HARD_ENG_MCP_NAME],
        { home, env },
        'Codex MCP remove',
      );
      actionDigest = digestValue({ action, name: HARD_ENG_MCP_NAME });
    }

    const after = readInventory(run, home, env);
    const afterState = classify(after.entries, home);
    const correct = desiredConfigured
      ? afterState.status === 'PASS' && afterState.codebase_memory_mcp_entries === 0
      : afterState.status === 'NOT_CONFIGURED' && afterState.codebase_memory_mcp_entries === 0;
    if (!correct) throw new Error('Codex MCP wiring did not reach the approved state.');
    return {
      status: 'PASS',
      action,
      changed: action !== 'none',
      evidence_digest: sha256(`${before.evidenceDigest}\0${actionDigest}\0${after.evidenceDigest}`),
    };
  }

  return { inspect, reconcile };
}
