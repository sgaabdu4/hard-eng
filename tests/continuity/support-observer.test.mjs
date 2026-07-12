import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { observeSupportReceipt } from '../../runtime/lib/support-observer.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

test('Codebase Memory receipts are generated from exact runtime commands, not caller digests', () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-support-observer-'));
  const calls = [];
  const execute = (command, args) => {
    calls.push([command, ...args]);
    if (args[1] === 'list_projects') return {
      ok: true,
      stdout: JSON.stringify({ projects: [{ name: 'fixture-project', root_path: repo }] }),
      stderr: '',
      evidence: '1'.repeat(64),
    };
    if (args[1] === 'detect_changes') return { ok: true, stdout: '{}', stderr: '', evidence: '2'.repeat(64) };
    throw new Error(`Unexpected support command: ${command} ${args.join(' ')}`);
  };
  const receipt = observeSupportReceipt(repo, {
    tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: 'f'.repeat(64),
  }, { now: NOW, execute });
  assert.equal(receipt.runtime_observed, true);
  assert.notEqual(receipt.evidence_digest, 'f'.repeat(64));
  assert.deepEqual(calls.map((call) => call.slice(0, 3)), [
    ['codebase-memory-mcp', 'cli', 'list_projects'],
    ['codebase-memory-mcp', 'cli', 'detect_changes'],
  ]);
});

test('Codebase Memory structural receipts execute a bounded exact-project graph query', () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-support-graph-'));
  const calls = [];
  const execute = (command, args) => {
    calls.push([command, ...args]);
    if (args[1] === 'list_projects') return {
      ok: true,
      stdout: JSON.stringify({ projects: [{ name: 'fixture-project', root_path: repo }] }),
      stderr: '',
      evidence: '5'.repeat(64),
    };
    if (args[1] === 'search_graph') return {
      ok: true, stdout: JSON.stringify({ results: [] }), stderr: '', evidence: '6'.repeat(64),
    };
    throw new Error(`Unexpected support command: ${command} ${args.join(' ')}`);
  };
  const receipt = observeSupportReceipt(repo, {
    tool: 'codebase-memory',
    operation: 'search_graph',
    status: 'pass',
    parameters: { name_pattern: '.*Observer.*', label: 'Function', limit: 12 },
    evidence_digest: 'f'.repeat(64),
  }, { now: NOW, execute });
  assert.equal(receipt.operation, 'search_graph');
  assert.equal(receipt.runtime_observed, true);
  assert.equal('parameters' in receipt, false);
  const query = JSON.parse(calls.at(-1)[3]);
  assert.deepEqual(query, {
    project: 'fixture-project', name_pattern: '.*Observer.*', label: 'Function', limit: 12,
  });
  assert.throws(() => observeSupportReceipt(repo, {
    tool: 'codebase-memory', operation: 'trace_path', status: 'pass',
    parameters: { function_name: 'owner', direction: 'both', depth: 9 },
  }, { now: NOW, execute }), /depth|bounded/i);
});

test('Context Mode pass and fallback dispositions execute an exact-project indexed search', () => {
  const calls = [];
  const healthy = (command, args) => {
    calls.push([command, ...args]);
    return {
    ok: true,
    stdout: '## 1. Indexed proof\nSource: build-log\n',
    stderr: '',
    evidence: '3'.repeat(64),
    };
  };
  const pass = observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'search', status: 'pass',
    parameters: { source: 'build-log', query: 'failed check', limit: 5 },
  }, { now: NOW, execute: healthy });
  assert.equal(pass.status, 'pass');
  assert.equal(pass.runtime_observed, true);
  assert.deepEqual(calls[0], [
    'context-mode', 'search', 'failed check', '--source', 'build-log',
    '--project', '/fixture', '--limit', '5',
  ]);
  assert.equal('parameters' in pass, false);
  assert.throws(() => observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'search', status: 'fallback', fallback_reason: 'fixture failure',
    parameters: { source: 'build-log', query: 'failed check' },
  }, { now: NOW, execute: healthy }), /fallback.*forbidden/i);

  const failed = () => ({ ok: false, stdout: '', stderr: 'private failure', evidence: '4'.repeat(64) });
  const fallback = observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'search', status: 'fallback', fallback_reason: 'Indexed search failed once',
    parameters: { source: 'build-log', query: 'failed check' },
  }, { now: NOW, execute: failed });
  assert.equal(fallback.status, 'fallback');
  assert.equal(fallback.evidence_digest, '4'.repeat(64));
  assert.doesNotMatch(JSON.stringify(fallback), /private failure/);
  assert.throws(() => observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'doctor', status: 'pass',
  }, { now: NOW, execute: healthy }), /indexed search|operation/i);
  assert.throws(() => observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'search', status: 'pass',
    parameters: { source: 'build-log', query: 'failed check' },
  }, {
    now: NOW,
    execute: () => ({
      ok: true, stdout: '## 1. Wrong source\nSource: another-log\n', stderr: '', evidence: '7'.repeat(64),
    }),
  }), /runtime observation failed|source/i);
});

test('Context Mode not-applicable is server-issued only for the exact no-large-output case', () => {
  const receipt = observeSupportReceipt('/fixture', {
    tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output',
  }, { now: NOW, execute: () => { throw new Error('must not run'); } });
  assert.equal(receipt.runtime_observed, true);
  assert.throws(() => observeSupportReceipt('/fixture', {
    tool: 'codebase-memory', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output',
  }, { now: NOW }), /only Context Mode/i);
});
