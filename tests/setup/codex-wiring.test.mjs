import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  HARD_ENG_MCP_NAME,
  createCodexWiringClient,
} from '../../runtime/lib/codex-wiring.mjs';

function expectedEntry(home) {
  return {
    name: HARD_ENG_MCP_NAME,
    enabled: true,
    disabled_reason: null,
    transport: {
      type: 'stdio',
      command: 'node',
      args: [path.join(path.resolve(home), '.agents', 'runtime', 'server.mjs')],
      cwd: null,
      env: {},
      env_vars: [],
    },
  };
}

function fakeCodex(initial = []) {
  const entries = new Map(initial.map((entry) => [entry.name, structuredClone(entry)]));
  const calls = [];
  function run(args, { home }) {
    calls.push([...args]);
    if (args.join(' ') === 'mcp list --json') {
      return { status: 0, stdout: JSON.stringify([...entries.values()]), stderr: '', error: null };
    }
    if (args[0] === 'mcp' && args[1] === 'add') {
      const [name, separator, command, ...commandArgs] = args.slice(2);
      if (separator !== '--') return { status: 2, stdout: '', stderr: 'missing separator', error: null };
      entries.set(name, {
        name,
        enabled: true,
        disabled_reason: null,
        transport: { type: 'stdio', command, args: commandArgs, cwd: null, env: {}, env_vars: [] },
      });
      return { status: 0, stdout: '', stderr: '', error: null };
    }
    if (args[0] === 'mcp' && args[1] === 'remove') {
      entries.delete(args[2]);
      return { status: 0, stdout: '', stderr: '', error: null };
    }
    return { status: 2, stdout: '', stderr: 'unsupported command', error: null };
  }
  return { calls, entries, run };
}

test('standalone wiring installs once, verifies the exact owner, and removes only itself', () => {
  const home = '/tmp/hard-eng-wiring-home';
  const unrelated = {
    name: 'context-mode',
    enabled: true,
    transport: { type: 'stdio', command: 'context-mode', args: [], cwd: null, env: {}, env_vars: [] },
  };
  const fake = fakeCodex([unrelated]);
  const client = createCodexWiringClient({ run: fake.run, env: { PATH: process.env.PATH } });

  assert.equal(client.inspect(home).status, 'NOT_CONFIGURED');
  const added = client.reconcile(home, true);
  assert.deepEqual({ status: added.status, action: added.action, changed: added.changed }, {
    status: 'PASS', action: 'add', changed: true,
  });
  assert.equal(client.inspect(home).status, 'PASS');
  assert.deepEqual(fake.entries.get(HARD_ENG_MCP_NAME), expectedEntry(home));

  const repeated = client.reconcile(home, true);
  assert.deepEqual({ status: repeated.status, action: repeated.action, changed: repeated.changed }, {
    status: 'PASS', action: 'none', changed: false,
  });

  const removed = client.reconcile(home, false);
  assert.deepEqual({ status: removed.status, action: removed.action, changed: removed.changed }, {
    status: 'PASS', action: 'remove', changed: true,
  });
  assert.equal(client.inspect(home).status, 'NOT_CONFIGURED');
  assert.deepEqual(fake.entries.get('context-mode'), unrelated);
});

test('standalone wiring refuses to replace or remove a mismatched owner', () => {
  const home = '/tmp/hard-eng-wiring-conflict';
  const conflicting = expectedEntry(home);
  conflicting.transport.args = ['./runtime/server.mjs'];
  conflicting.transport.cwd = '/another/owner';
  const fake = fakeCodex([conflicting]);
  const client = createCodexWiringClient({ run: fake.run });

  const report = client.inspect(home);
  assert.equal(report.status, 'CONFLICT');
  assert.equal(report.configured, true);
  assert.equal(report.owned, false);
  assert.throws(() => client.reconcile(home, true), /unexpected hard_eng owner/i);
  assert.throws(() => client.reconcile(home, false), /unexpected hard_eng owner/i);
  assert.deepEqual(fake.entries.get(HARD_ENG_MCP_NAME), conflicting);
  assert.equal(fake.calls.some((args) => args[1] === 'add' || args[1] === 'remove'), false);
});

test('standalone wiring classifies the installed-cache owner but delegates its cutover', () => {
  const home = '/tmp/hard-eng-wiring-cutover';
  const installedCache = {
    name: HARD_ENG_MCP_NAME,
    enabled: true,
    disabled_reason: null,
    transport: {
      type: 'stdio',
      command: 'node',
      args: ['./runtime/server.mjs'],
      cwd: path.join(home, '.codex', 'plugins', 'cache', 'personal', 'hard-eng', '1.0.0', '.'),
      env: {},
      env_vars: [],
    },
  };
  const fake = fakeCodex([installedCache]);
  const client = createCodexWiringClient({ run: fake.run });

  assert.equal(client.inspect(home).status, 'MIGRATION_REQUIRED');
  assert.throws(() => client.reconcile(home, true), /approved live cutover/i);
  assert.throws(() => client.reconcile(home, false), /approved live cutover/i);
  assert.deepEqual(fake.entries.get(HARD_ENG_MCP_NAME), installedCache);
  assert.equal(fake.calls.some((args) => args[0] === 'mcp' && ['add', 'remove'].includes(args[1])), false);
});

test('standalone wiring fails closed on duplicate names or invalid Codex JSON', () => {
  const home = '/tmp/hard-eng-wiring-invalid';
  const duplicate = expectedEntry(home);
  const duplicateRun = (args) => ({
    status: 0,
    stdout: JSON.stringify([duplicate, duplicate]),
    stderr: '',
    error: null,
  });
  assert.equal(createCodexWiringClient({ run: duplicateRun }).inspect(home).status, 'FAIL');

  const invalidRun = () => ({ status: 0, stdout: '{', stderr: '', error: null });
  const invalid = createCodexWiringClient({ run: invalidRun }).inspect(home);
  assert.equal(invalid.status, 'FAIL');
  assert.match(invalid.evidence_digest, /^[a-f0-9]{64}$/);
});

test('standalone wiring evidence binds semantic inventory instead of volatile JSON bytes', () => {
  const home = '/tmp/hard-eng-wiring-semantic-evidence';
  const entry = expectedEntry(home);
  let calls = 0;
  const run = () => {
    calls += 1;
    return {
      status: 0,
      stdout: calls % 2 === 0 ? JSON.stringify([entry], null, 2) : JSON.stringify([entry]),
      stderr: calls % 2 === 0 ? 'successful diagnostic formatting\n' : '',
      error: null,
    };
  };
  const client = createCodexWiringClient({ run });
  const first = client.inspect(home);
  const second = client.inspect(home);
  assert.equal(first.status, 'PASS');
  assert.equal(second.status, 'PASS');
  assert.equal(first.evidence_digest, second.evidence_digest);
});

test('standalone wiring inventory reports Codebase Memory MCP registrations separately', () => {
  const home = '/tmp/hard-eng-wiring-codebase-memory';
  const codebaseMemory = {
    name: 'graph-cache',
    enabled: true,
    transport: {
      type: 'stdio', command: '/tmp/codebase-memory-mcp', args: [], cwd: null, env: {}, env_vars: [],
    },
  };
  const report = createCodexWiringClient({ run: fakeCodex([codebaseMemory]).run }).inspect(home);
  assert.equal(report.status, 'NOT_CONFIGURED');
  assert.equal(report.codebase_memory_mcp_entries, 1);
  assert.match(report.codebase_memory_mcp_evidence_digest, /^[a-f0-9]{64}$/);
});

test('standalone wiring refuses to mutate around a Codebase Memory MCP registration', () => {
  const home = '/tmp/hard-eng-wiring-codebase-memory-blocked';
  const codebaseMemory = {
    name: 'codebase-memory-mcp',
    enabled: true,
    transport: {
      type: 'stdio', command: '/tmp/codebase-memory-mcp', args: [], cwd: null, env: {}, env_vars: [],
    },
  };
  const fake = fakeCodex([codebaseMemory]);
  const client = createCodexWiringClient({ run: fake.run });

  assert.throws(() => client.reconcile(home, true), /approved.*retirement/i);
  assert.equal(fake.entries.has(HARD_ENG_MCP_NAME), false);
  assert.equal(fake.calls.some((args) => args[0] === 'mcp' && ['add', 'remove'].includes(args[1])), false);
});
