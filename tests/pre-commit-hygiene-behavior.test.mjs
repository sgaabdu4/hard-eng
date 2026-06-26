#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const install = fs.readFileSync(path.join(repo, 'scripts', 'install.sh'), 'utf8');
const match = install.match(/install_hook pre-commit <<'EOF'\n([\s\S]*?)\nEOF/);
assert.ok(match, 'install.sh must contain a pre-commit hook heredoc');
const hookBody = match[1];
const token = ['github', '_pat_', 'A'.repeat(24)].join('');

function sh(command, cwd) {
  const result = spawnSync('bash', ['-lc', command], { cwd, encoding: 'utf8' });
  assert.equal(result.status, 0, `${command}\n${result.stderr}`);
  return result;
}

function makeRepo() {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-hook-'));
  const root = path.join(parent, '.agents');
  fs.mkdirSync(root);
  sh('git init -q && git config user.email test.invalid && git config user.name Test', root);
  const scripts = path.join(root, 'scripts');
  fs.mkdirSync(scripts);
  for (const name of [
    'check-markdown-hygiene.mjs',
    'check-project-naming.mjs',
    'check-generated-assets.mjs',
    'check-ssot-guardrails.mjs',
  ]) {
    const file = path.join(scripts, name);
    fs.writeFileSync(file, '#!/usr/bin/env node\nprocess.exit(0);\n');
    fs.chmodSync(file, 0o755);
  }
  const hook = path.join(root, '.git', 'hooks', 'pre-commit');
  fs.writeFileSync(hook, hookBody);
  fs.chmodSync(hook, 0o755);
  return root;
}

function stage(root, relativePath, content) {
  const file = path.join(root, relativePath);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
  sh(`git add -- ${JSON.stringify(relativePath)}`, root);
}

function runHook(root, extraEnv = {}) {
  return spawnSync(path.join(root, '.git', 'hooks', 'pre-commit'), {
    cwd: root,
    env: { ...process.env, HOME: path.join(root, 'home'), ...extraEnv },
    encoding: 'utf8',
  });
}

for (const [relativePath, content, expected] of [
  ['.env', 'API_KEY=value\n', /staged forbidden files/],
  ['generated/out.txt', 'generated file\n', /staged forbidden files/],
  ['src/generated-marker.txt', ['AUTO', '-GENERATED file\n'].join(''), /staged forbidden files/],
  ['src/big.txt', `${'x\n'.repeat(701)}`, /over 700 lines/],
  ['src/secret.txt', `${token}\n`, /secret-like values/],
]) {
  const root = makeRepo();
  stage(root, relativePath, content);
  const result = runHook(root);
  assert.notEqual(result.status, 0, `${relativePath} should be blocked`);
  assert.match(result.stdout, expected);
}

{
  const root = makeRepo();
  const homePath = path.join(root, 'home');
  stage(root, 'src/home.txt', `${homePath}\n`);
  const result = runHook(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /private project\/local path references/);
}

{
  const root = makeRepo();
  stage(root, 'src/private.txt', 'PRIVATE_PROJECT_TOKEN\n');
  const result = runHook(root, { HARD_ENG_PRIVATE_CONTENT_PATTERN: 'PRIVATE_PROJECT_TOKEN' });
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /private project\/local path references/);
}

{
  const root = makeRepo();
  stage(root, 'src/blob.bin', Buffer.concat([Buffer.from([0]), Buffer.from(token)]));
  const result = runHook(root);
  assert.equal(result.status, 0, result.stdout + result.stderr);
}

{
  const root = makeRepo();
  sh(`git update-index --add --cacheinfo 160000,${'a'.repeat(40)},vendor/submodule`, root);
  const result = runHook(root);
  assert.equal(result.status, 0, result.stdout + result.stderr);
}

console.log('pre-commit-hygiene-behavior-test: pass');
