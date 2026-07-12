import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');
const textExtensions = new Set([
  '.css', '.json', '.md', '.mjs', '.py', '.sh', '.svg', '.toml', '.yaml', '.yml',
]);

function sourceFiles() {
  return execFileSync('git', [
    '-C', root, 'ls-files', '--cached', '--others', '--exclude-standard', '-z',
  ]).toString('utf8').split('\0').filter(Boolean).sort();
}

function ownedTextFiles() {
  return sourceFiles().filter((relative) => {
    if (relative.startsWith('tests/') || relative.startsWith('vendor/')) return false;
    const target = path.join(root, relative);
    return textExtensions.has(path.extname(relative))
      && fs.existsSync(target)
      && fs.lstatSync(target).isFile();
  });
}

function mentionFiles(term) {
  const needle = term.toLowerCase();
  return ownedTextFiles().filter((relative) => fs.readFileSync(path.join(root, relative), 'utf8')
    .toLowerCase().includes(needle));
}

test('retired dependency, foreign-harness, plugin, and old-eval paths remain absent', () => {
  const files = sourceFiles();
  for (const relative of [
    '.claude', '.pi', 'agents', 'codex', 'integrations', 'plugins',
    'tests/plugin', 'tests/v2',
  ]) {
    assert.equal(fs.existsSync(path.join(root, relative)), false, `retired physical root returned: ${relative}`);
  }

  for (const relative of files) {
    const parts = relative.split('/');
    assert.equal(parts.includes('evals'), false, `old model-eval root returned: ${relative}`);
    assert.equal(parts.includes('.codex-plugin'), false, `plugin manifest returned: ${relative}`);
    assert.equal(parts.some((part) => ['no-mistakes', 'treehouse', 'impeccable'].includes(part)), false,
      `retired dependency path returned: ${relative}`);
    assert.equal(['CLAUDE.md', 'GEMINI.md', 'PI.md', 'marketplace.json', '.no-mistakes.yaml']
      .includes(path.basename(relative)), false, `retired harness/config returned: ${relative}`);
  }
});

test('retired tool names are confined to exact migration evidence and negative guards', () => {
  const expected = new Map([
    ['no-mistakes', [
      'THIRD_PARTY_NOTICES.md',
      'runtime/lib/approved-cutover-inventory.mjs',
      'runtime/lib/check-registry.mjs',
      'runtime/lib/legacy-control-plane.mjs',
      'runtime/lib/requirement-proofs.mjs',
      'runtime/lib/setup-doctor.mjs',
      'runtime/lib/skill-parity.mjs',
    ]],
    ['treehouse', [
      'runtime/lib/approved-cutover-inventory.mjs',
      'runtime/lib/check-registry.mjs',
      'runtime/lib/legacy-control-plane.mjs',
      'runtime/lib/requirement-proofs.mjs',
      'runtime/lib/setup-doctor.mjs',
      'runtime/lib/skill-parity.mjs',
    ]],
    ['impeccable', [
      'runtime/lib/approved-cutover-inventory.mjs',
      'runtime/lib/requirement-proofs.mjs',
      'runtime/lib/skill-parity.mjs',
    ]],
    ['claude', [
      'runtime/lib/check-registry.mjs',
      'runtime/lib/setup-doctor.mjs',
    ]],
    ['gemini', []],
  ]);
  for (const [term, files] of expected) assert.deepEqual(mentionFiles(term), files, `${term} leaked`);

  for (const marker of [
    'he-state.json', 'session_state.md', 'mcp__codebase_memory_mcp', '/he:implement', '/he:verify',
  ]) {
    assert.deepEqual(mentionFiles(marker), [], `retired runtime marker returned: ${marker}`);
  }
});

test('active native skills and executable entrypoints cannot route through retired surfaces', () => {
  const active = sourceFiles().filter((relative) => (
    relative.startsWith('skills/')
    || relative.startsWith('scripts/')
    || relative.startsWith('hooks/')
    || relative.startsWith('.github/')
    || relative === 'package.json'
  ));
  const forbidden = /no-mistakes|treehouse|impeccable|workflow-help|grill-me|he-implement|he-verify|mcp__codebase_memory|\bclaude\b|\bgemini\b/i;
  for (const relative of active) {
    const target = path.join(root, relative);
    if (!fs.existsSync(target) || !fs.lstatSync(target).isFile()) continue;
    assert.doesNotMatch(fs.readFileSync(target, 'utf8'), forbidden, `retired route returned: ${relative}`);
  }

  const modules = fs.readFileSync(path.join(root, '.gitmodules'), 'utf8');
  assert.doesNotMatch(modules, /no-mistakes|treehouse|impeccable/i);
});
