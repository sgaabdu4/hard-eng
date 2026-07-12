import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { redactErrorMessage } from '../../runtime/lib/redact.mjs';

test('protocol error redaction removes paths, credentials, controls, and excess output', () => {
  const apiKey = `sk-${'A'.repeat(32)}`;
  const github = `ghp_${'B'.repeat(32)}`;
  const input = [
    "open '/Users/example/My Project/private.env'",
    'from /Volumes/Private/data.json',
    'and file:///private/tmp/session/state.json',
    String.raw`plus C:\Users\example\Secrets\key.pem`,
    `Bearer ${apiKey}`,
    github,
    'password=hunter2',
    'https://person:pass@example.test/private',
    `\n${'x'.repeat(900)}`,
  ].join(' ');
  const output = redactErrorMessage(new Error(input));

  for (const forbidden of [
    '/Users/example', '/Volumes/Private', 'file:///private', String.raw`C:\Users`,
    apiKey, github, 'hunter2', 'person:pass', '\n',
  ]) assert.doesNotMatch(output, new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(output, /<path>/);
  assert.match(output, /<redacted>/);
  assert.ok(output.length <= 512);
});

test('protocol error redaction preserves bounded actionable lifecycle messages', () => {
  assert.equal(
    redactErrorMessage(new Error('Accepted plan digest changed; Plan reconciliation is required.')),
    'Accepted plan digest changed; Plan reconciliation is required.',
  );
});

test('setup CLI failures never print the selected absolute home', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-private-home-'));
  const result = spawnSync(process.execPath, [
    path.resolve('scripts/setup.mjs'), 'rollback', '--home', home,
    '--backup', 'a'.repeat(64), '--dry-run',
  ], { encoding: 'utf8' });
  assert.equal(result.status, 2);
  assert.doesNotMatch(result.stderr, new RegExp(home.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(result.stderr, /<path>/);
});
