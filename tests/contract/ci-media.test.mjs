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
  assert.equal((text.match(/node runtime\/he\.mjs check --all/g) ?? []).length, 1);
  assert.doesNotMatch(text, /npm install|curl|wget|codex exec|continue-on-error/i);
});

test('README hero and Verified Return marks are accessible and sanitized', () => {
  const heroRelative = 'assets/readme/hard-eng-hero.png';
  const hero = fs.readFileSync(path.join(root, heroRelative));
  const wordmark = fs.readFileSync(path.join(root, 'assets/readme/hard-eng-wordmark.svg'), 'utf8');
  const icon = fs.readFileSync(path.join(root, 'assets/readme/hard-eng.svg'), 'utf8');
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  assert.equal(hero.subarray(1, 4).toString('ascii'), 'PNG');
  assert.equal(hero.readUInt32BE(16), 1672);
  assert.equal(hero.readUInt32BE(20), 941);
  assert.ok(readme.includes(`](${heroRelative})`));
  assert.deepEqual(fs.readdirSync(path.join(root, 'assets/readme')).sort(), [
    'hard-eng-hero.png',
    'hard-eng-wordmark.svg',
    'hard-eng.svg',
    'tokens.css',
  ]);

  for (const svg of [wordmark, icon]) {
    assert.match(svg, /<svg[^>]+role="img"[^>]+aria-labelledby="title desc"/);
    assert.match(svg, /<title id="title">[^<]+<\/title>/);
    assert.match(svg, /<desc id="desc">[^<]+<\/desc>/);
    assert.doesNotMatch(svg, /\/Users\/|\.env|token|task[_ -]?id|github\.com/i);
  }
  assert.match(wordmark, /proof-return arrow/);
  assert.doesNotMatch(wordmark, /<text\b|font-family=/);
  assert.match(icon, /#171c22/);
  assert.match(icon, /#0d7f84/);
  assert.doesNotMatch(icon, /<rect\b|filter=|gradient/i);
});
