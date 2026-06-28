#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-generated-assets.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'generated-assets-'));
const config = path.join(tmp, 'generated-assets.json');
const html = path.join(tmp, 'docs/project-workflow-gates.html');
const png = path.join(tmp, 'docs/images/project-workflow-gates.png');
const media = path.join(tmp, 'docs/media/demo.mp4');
const gif = path.join(tmp, 'docs/media/demo.gif');

function write(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}

function writeBinary(file, buffer) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, buffer);
}

function pngWithChunk(type, data = '') {
  const chunks = [];
  function addChunk(name, payload) {
    const body = Buffer.from(payload);
    const header = Buffer.alloc(8);
    header.writeUInt32BE(body.length, 0);
    header.write(name, 4, 4, 'latin1');
    chunks.push(header, body, Buffer.alloc(4));
  }
  addChunk('IHDR', Buffer.alloc(13));
  addChunk(type, data);
  addChunk('IEND', '');
  return Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), ...chunks]);
}

function run() {
  return spawnSync('node', [script, tmp], { encoding: 'utf8' });
}

write(html, '<!doctype html><title>Hard Eng</title>\n');
write(config, `${JSON.stringify({ pairs: [{ source: 'docs/project-workflow-gates.html', output: 'docs/images/project-workflow-gates.png' }] }, null, 2)}\n`);
let result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /missing/);

write(png, 'png');
const old = new Date(Date.now() - 5000);
fs.utimesSync(png, old, old);
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /older than/);

write(png, 'fresh-png');
result = run();
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /generated-assets: pass/);

fs.rmSync(html);
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /missing for docs\/images\/project-workflow-gates\.png/);

write(html, '<!doctype html><title>Hard Eng</title>\n');
write(path.join(tmp, 'README.md'), '<img src="docs/images/unregistered.png" alt="missing">\n');
write(path.join(tmp, 'docs/images/unregistered.png'), 'png');
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /referenced by README\.md but missing from generated-assets\.json/);

write(path.join(tmp, 'README.md'), '[Watch](docs/media/demo.mp4)\n');
write(media, 'mp4');
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /docs\/media\/demo\.mp4 is referenced by README\.md but missing from generated-assets\.json/);

write(config, `${JSON.stringify({
  pairs: [{ source: 'docs/project-workflow-gates.html', output: 'docs/images/project-workflow-gates.png' }],
  static: [{ output: 'docs/media/demo.mp4', reason: 'test media' }],
}, null, 2)}\n`);
result = run();
assert.equal(result.status, 0, result.stderr);

write(path.join(tmp, 'README.md'), '![Flow](docs/media/demo.gif)\n');
write(gif, 'gif');
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /docs\/media\/demo\.gif is referenced by README\.md but missing from generated-assets\.json/);

write(config, `${JSON.stringify({
  pairs: [{ source: 'docs/project-workflow-gates.html', output: 'docs/images/project-workflow-gates.png' }],
  static: [
    { output: 'docs/media/demo.mp4', reason: 'test media' },
    { output: 'docs/media/demo.gif', reason: 'test gif' },
  ],
}, null, 2)}\n`);
result = run();
assert.equal(result.status, 0, result.stderr);

const hero = path.join(tmp, 'docs/images/hero.png');
write(path.join(tmp, 'README.md'), '<img src="docs/images/hero.png" alt="hero">\n');
writeBinary(hero, pngWithChunk('caBX', 'OpenAI Media Service API'));
write(config, `${JSON.stringify({
  pairs: [{ source: 'docs/project-workflow-gates.html', output: 'docs/images/project-workflow-gates.png' }],
  static: [
    { output: 'docs/media/demo.mp4', reason: 'test media' },
    { output: 'docs/media/demo.gif', reason: 'test gif' },
    { output: 'docs/images/hero.png', reason: 'test image' },
  ],
}, null, 2)}\n`);
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /caBX provenance metadata/);

writeBinary(hero, pngWithChunk('tEXt', '/Users/example/private-app'));
result = run();
assert.notEqual(result.status, 0);
assert.match(result.stderr, /private or secret-like PNG text metadata/);

console.log('generated-assets-test: pass');
