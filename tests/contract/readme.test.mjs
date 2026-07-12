import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');

function shellBlocks(text) {
  return [...text.matchAll(/```sh\n([\s\S]*?)```/g)].map((match) => match[1].trim());
}

function makeShims(directory, log) {
  fs.mkdirSync(directory, { recursive: true });
  const body = '#!/bin/sh\nprintf "%s\\t%s\\n" "$(basename "$0")" "$*" >> "$HARD_ENG_COMMAND_LOG"\n';
  for (const command of ['he', 'codebase-memory-mcp', 'context-mode', 'node', 'npm']) {
    const file = path.join(directory, command);
    fs.writeFileSync(file, body, { mode: 0o755 });
  }
  fs.writeFileSync(log, '');
}

function instantiate(block, fixture) {
  const values = {
    '<run-id>': 'run-fixture',
    '<relative-file>': 'notes.txt',
    '<absolute-repository-path>': fixture,
    '<project-id>': 'fixture-project',
    '<path>': 'evidence.txt',
    '<label>': 'fixture-evidence',
    '<query>': 'failed check',
    '<plan-digest>': 'a'.repeat(64),
    '<rollback-bundle-digest>': 'b'.repeat(64),
    '<exact-relative-path>': '.env.local',
    '<exact-state-root>': path.join(fixture, '.git', 'common', 'hard-eng', 'v1'),
  };
  return Object.entries(values).reduce((text, [placeholder, value]) => text.replaceAll(placeholder, value), block);
}

test('README is the complete five-minute interface and contains no private values', () => {
  for (const heading of [
    'Pick the smallest route', 'The five-minute flow', 'State, compaction, and resume',
    'Codebase Memory and Context Mode are required support tools', 'Setup',
    'Cost guarantees', 'Codex worktrees and ignored local files',
    'Troubleshooting', 'Uninstall',
  ]) assert.match(readme, new RegExp(`^## ${heading}$`, 'm'));
  assert.match(readme, /Build and Verify in one loop/);
  assert.match(readme, /Plan includes a complete inspectable flow/);
  assert.match(readme, /Learn is an interrupt, not a compulsory ceremony/);
  assert.match(readme, /Imagegen defaults to zero calls/);
  assert.match(readme, /cli index_repository '\{"repo_path":"<absolute-repository-path>"\}'/);
  assert.match(readme, /context-mode search "<query>" --source <label> --project <absolute-repository-path> --limit 10/);
  assert.match(readme, /manual MCP entry exposes the\s+tools without enabling global routing/);
  assert.match(readme, /six global Codex plugin hooks are\s+optional/);
  assert.match(readme, /rollback --backup <rollback-bundle-digest> --dry-run/);
  assert.match(readme, /recover --dry-run/);
  assert.match(readme, /purge-state --state-root <exact-state-root> --dry-run/);
  assert.match(readme, /codex plugin add hard-eng@personal --json/);
  assert.match(readme, /default `~\/.codex`/);
  assert.match(readme, /server executes the requested bounded graph command/i);
  assert.match(readme, /Codex copies approved\s+entries at managed-worktree creation/i);
  assert.match(readme, /live `git ls-remote`/);
  assert.match(readme, /unresolved review threads/i);
  assert.match(readme, /Bundle directories are `0700`/);
  assert.match(readme, /renaming only its Hard Eng ownership markers/);
  assert.match(readme, /no-mistakes dependencies, and Treehouse retirement appear\s+as explicit blockers/);
  assert.doesNotMatch(readme, /\/Users\/|task[_ -]?id|access[_ -]?token|github\.com\/[^)\s]+\/[^)\s]+\/pull\//i);
});

test('every README shell command is syntax-checked and exercised through a fixture', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-readme-'));
  const bin = path.join(fixture, 'bin');
  const log = path.join(fixture, 'commands.log');
  makeShims(bin, log);
  const blocks = shellBlocks(readme);
  assert.ok(blocks.length >= 9);
  let expectedLines = 0;
  for (const raw of blocks) {
    const block = instantiate(raw, fixture);
    assert.doesNotMatch(block, /<[^>]+>/, `untested placeholder in:\n${raw}`);
    execFileSync('/bin/sh', ['-n', '-c', block]);
    execFileSync('/bin/sh', ['-c', block], {
      cwd: fixture,
      env: { ...process.env, HOME: fixture, PATH: `${bin}:${process.env.PATH}`, HARD_ENG_COMMAND_LOG: log },
    });
    expectedLines += block.split(/\r?\n/).filter((line) => line.trim()).length;
  }
  const calls = fs.readFileSync(log, 'utf8').trim().split(/\r?\n/).filter(Boolean);
  assert.equal(calls.length, expectedLines);
  assert.deepEqual([...new Set(calls.map((line) => line.split('\t')[0]))].sort(), [
    'codebase-memory-mcp', 'context-mode', 'he', 'node', 'npm',
  ]);
});
