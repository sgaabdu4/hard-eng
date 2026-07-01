#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const checker = path.join(repo, 'scripts', 'check-markdown-hygiene.mjs');
const gitignore = fs.readFileSync(path.join(repo, '.gitignore'), 'utf8');

assert.match(gitignore, /^\/outputs\/$/m);
assert.match(gitignore, /^\/tmp\/$/m);
assert.doesNotMatch(gitignore, /^outputs\/$/m);
assert.doesNotMatch(gitignore, /^tmp\/$/m);

const pass = spawnSync(checker, {
  cwd: repo,
  encoding: 'utf8',
});
assert.equal(pass.status, 0, `markdown hygiene should pass current repo:\n${pass.stderr}`);
assert.match(pass.stdout, /markdown-hygiene: pass/);

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-'));
fs.mkdirSync(path.join(tmp, 'skills', 'demo'), { recursive: true });
fs.writeFileSync(
  path.join(tmp, 'AGENTS.md'),
  '# Agent Rules\n\n## Stops\nThis arbitrary explanation is not a rule and should fail.\n- Rule\n',
);
fs.writeFileSync(path.join(tmp, 'skills', 'demo', 'SKILL.md'), '# Demo\n');

const fail = spawnSync(checker, {
  cwd: tmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: tmp },
  encoding: 'utf8',
});
assert.notEqual(fail.status, 0, 'checker must fail prompt prose in AGENTS.md');
assert.match(fail.stderr, /free prose/);
assert.match(fail.stderr, /bullet, heading, or fenced template/);

const skillTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-skill-'));
fs.mkdirSync(path.join(skillTmp, 'skills', 'demo'), { recursive: true });
fs.writeFileSync(path.join(skillTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(
  path.join(skillTmp, 'skills', 'demo', 'SKILL.md'),
  [
    '---',
    'name: demo',
    'description: Use for a very long skill description that tries to list every possible trigger phrase, workflow, edge case, role, artifact, and implementation detail in metadata.',
    '---',
    '',
    '# Demo',
    '',
  ].join('\n'),
);
const skillFail = spawnSync(checker, {
  cwd: skillTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: skillTmp },
  encoding: 'utf8',
});
assert.notEqual(skillFail.status, 0, 'checker must fail bloated skill descriptions');
assert.match(skillFail.stderr, /description must stay at or under 30 tokens/);

const leakTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-leak-'));
fs.writeFileSync(path.join(leakTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(path.join(leakTmp, 'README.md'), `This session said to use ${os.homedir()}/tmp.\n`);
const leak = spawnSync(checker, {
  cwd: leakTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: leakTmp },
  encoding: 'utf8',
});
assert.notEqual(leak.status, 0, 'checker must fail ownerless leakage in any Markdown file');
assert.match(leak.stderr, /local machine path requires explicit/);
assert.match(leak.stderr, /conversation state requires explicit/);

const markerTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-marker-'));
fs.writeFileSync(path.join(markerTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(
  path.join(markerTmp, 'README.md'),
  [
    '<!-- markdown-hygiene: allow-setup-internals -->',
    '',
    'README documents codex-watchdog setup behavior.',
    '',
  ].join('\n'),
);
const markerPass = spawnSync(checker, {
  cwd: markerTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: markerTmp },
  encoding: 'utf8',
});
assert.equal(markerPass.status, 0, `checker must allow hidden markdown-hygiene markers:\n${markerPass.stderr}`);

const bulletTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-bullet-'));
fs.writeFileSync(path.join(bulletTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(path.join(bulletTmp, 'README.md'), '- No trailing full stop.\n');
const bulletFail = spawnSync(checker, {
  cwd: bulletTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: bulletTmp },
  encoding: 'utf8',
});
assert.notEqual(bulletFail.status, 0, 'checker must fail bullets ending with full stops');
assert.match(bulletFail.stderr, /bullet must not end with a full stop/);

const workflowTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-workflow-'));
fs.mkdirSync(path.join(workflowTmp, 'skills', 'demo'), { recursive: true });
fs.writeFileSync(path.join(workflowTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(
  path.join(workflowTmp, 'skills', 'demo', 'SKILL.md'),
  [
    '---',
    'name: demo',
    'description: Use for demo checks.',
    '---',
    '',
    '# Demo',
    '',
    '1. First',
    '2. Second',
    '3. Third',
    '',
  ].join('\n'),
);
const workflowFail = spawnSync(checker, {
  cwd: workflowTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: workflowTmp },
  encoding: 'utf8',
});
assert.notEqual(workflowFail.status, 0, 'checker must fail 3+ step workflows in SKILL.md');
assert.match(workflowFail.stderr, /3\+ step workflow/);

const fencedTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-fenced-'));
fs.mkdirSync(path.join(fencedTmp, 'skills', 'demo'), { recursive: true });
fs.writeFileSync(path.join(fencedTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(
  path.join(fencedTmp, 'skills', 'demo', 'SKILL.md'),
  [
    '---',
    'name: demo',
    'description: Use for demo checks.',
    '---',
    '',
    '# Demo',
    '',
    '```md',
    '1. First',
    '2. Second',
    '3. Third',
    '```',
    '',
  ].join('\n'),
);
const fencedPass = spawnSync(checker, {
  cwd: fencedTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: fencedTmp },
  encoding: 'utf8',
});
assert.equal(fencedPass.status, 0, `checker must ignore numbered fenced examples:\n${fencedPass.stderr}`);

const artifactTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'markdown-hygiene-artifacts-'));
fs.mkdirSync(path.join(artifactTmp, 'outputs'), { recursive: true });
fs.mkdirSync(path.join(artifactTmp, 'tmp'), { recursive: true });
fs.writeFileSync(path.join(artifactTmp, 'AGENTS.md'), '# Agent Rules\n\n## Stops\n- Rule\n');
fs.writeFileSync(path.join(artifactTmp, 'outputs', 'deck.md'), '- Generated bullet with full stop.\n');
fs.writeFileSync(path.join(artifactTmp, 'tmp', 'scratch.md'), `This session used ${os.homedir()}/scratch.\n`);
const artifactPass = spawnSync(checker, {
  cwd: artifactTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: artifactTmp },
  encoding: 'utf8',
});
assert.equal(artifactPass.status, 0, `checker must ignore artifact and scratch roots:\n${artifactPass.stderr}`);

fs.mkdirSync(path.join(artifactTmp, 'docs', 'outputs'), { recursive: true });
fs.mkdirSync(path.join(artifactTmp, 'docs', 'tmp'), { recursive: true });
fs.writeFileSync(path.join(artifactTmp, 'docs', 'outputs', 'nested.md'), '- Nested project bullet with full stop.\n');
fs.writeFileSync(path.join(artifactTmp, 'docs', 'tmp', 'nested.md'), `This session used ${os.homedir()}/scratch.\n`);
const nestedArtifactFail = spawnSync(checker, {
  cwd: artifactTmp,
  env: { ...process.env, AGENTS_HYGIENE_ROOT: artifactTmp },
  encoding: 'utf8',
});
assert.notEqual(nestedArtifactFail.status, 0, 'checker must scan nested outputs/tmp directories');
assert.match(nestedArtifactFail.stderr, /docs\/outputs\/nested\.md/);
assert.match(nestedArtifactFail.stderr, /docs\/tmp\/nested\.md/);

console.log('markdown-hygiene-test: pass');
