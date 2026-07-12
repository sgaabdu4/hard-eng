import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');

test('one CI workflow invokes the same canonical check registry with pinned actions', () => {
  const directory = path.join(root, '.github', 'workflows');
  const workflows = fs.readdirSync(directory).filter((name) => /\.ya?ml$/.test(name));
  assert.deepEqual(workflows, ['hard-eng.yml']);
  const text = fs.readFileSync(path.join(directory, workflows[0]), 'utf8');
  assert.match(text, /permissions:\n  contents: read/);
  assert.match(text, /actions\/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6/);
  assert.match(text, /actions\/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e # v6/);
  assert.match(text, /node-version: 24/);
  assert.equal((text.match(/node plugins\/hard-eng\/runtime\/he\.mjs check --all/g) ?? []).length, 1);
  assert.doesNotMatch(text, /npm install|curl|wget|codex exec|continue-on-error/i);
});

test('README media is accessible, code-native, and sanitized', () => {
  const relative = 'assets/readme/hard-eng-flow.svg';
  const svg = fs.readFileSync(path.join(root, relative), 'utf8');
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  assert.ok(readme.includes(`![Hard Eng flow](${relative})`));
  assert.match(svg, /<svg[^>]+role="img"[^>]+aria-labelledby="title desc"/);
  assert.match(svg, /<title id="title">[^<]+<\/title>/);
  assert.match(svg, /<desc id="desc">[^<]+<\/desc>/);
  assert.match(svg, /Build ⇄ Verify/);
  assert.doesNotMatch(svg, /\/Users\/|\.env|token|task[_ -]?id|github\.com/i);
  assert.equal(fs.readdirSync(path.join(root, 'assets', 'readme')).length, 1);
});
