#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const script = path.join(repo, 'scripts', 'format-hard-eng.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'format-hard-eng-'));
const fixture = path.join(tmp, 'fixture');
const fallbackFixture = path.join(tmp, 'fallback-fixture');
const outside = path.join(tmp, 'outside.md');
const owned = path.join(fixture, 'owned.md');
const typedOwned = [
  'owned.ts',
  'owned.tsx',
  'owned.jsx',
  'owned.mts',
  'owned.cts',
].map((file) => path.join(fixture, file));
const link = path.join(fixture, 'link.md');
const invalidUtf8 = path.join(fixture, 'invalid.md');
const fallbackOwned = path.join(fallbackFixture, 'owned.md');
const fallbackGenerated = path.join(fallbackFixture, 'generated', 'out.md');
const fallbackNestedGenerated = path.join(fallbackFixture, 'src', 'generated', 'out.md');
const fallbackEvalsResult = path.join(fallbackFixture, 'tests', 'skills', 'e2e', 'evals', 'results', 'out.md');

fs.mkdirSync(fixture, { recursive: true });
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: fixture, encoding: 'utf8' });
fs.writeFileSync(outside, 'external   \n');
fs.writeFileSync(owned, 'owned   ');
for (const file of typedOwned) fs.writeFileSync(file, 'export const value = 1;   ');
fs.symlinkSync(outside, link);
const invalidUtf8Bytes = Buffer.from([0x66, 0x6f, 0x80, 0x20, 0x20, 0x20]);
fs.writeFileSync(invalidUtf8, invalidUtf8Bytes);

assert.equal(fs.lstatSync(link).isSymbolicLink(), true);

const result = spawnSync(process.execPath, [script, fixture], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.equal(fs.readFileSync(owned, 'utf8'), 'owned\n');
for (const file of typedOwned) assert.equal(fs.readFileSync(file, 'utf8'), 'export const value = 1;\n');
assert.equal(fs.readFileSync(outside, 'utf8'), 'external   \n');
assert.deepEqual(fs.readFileSync(invalidUtf8), invalidUtf8Bytes, 'invalid UTF-8 text must remain byte-for-byte unchanged');

fs.mkdirSync(path.dirname(fallbackGenerated), { recursive: true });
fs.mkdirSync(path.dirname(fallbackNestedGenerated), { recursive: true });
fs.mkdirSync(path.dirname(fallbackEvalsResult), { recursive: true });
fs.writeFileSync(fallbackOwned, 'owned   ');
fs.writeFileSync(fallbackGenerated, 'generated   ');
fs.writeFileSync(fallbackNestedGenerated, 'nested generated   ');
fs.writeFileSync(fallbackEvalsResult, 'eval result   ');

const fallbackResult = spawnSync(process.execPath, [script, fallbackFixture], { encoding: 'utf8' });
assert.equal(fallbackResult.status, 0, fallbackResult.stderr || fallbackResult.stdout);
assert.equal(fs.readFileSync(fallbackOwned, 'utf8'), 'owned\n');
assert.equal(fs.readFileSync(fallbackGenerated, 'utf8'), 'generated   ');
assert.equal(fs.readFileSync(fallbackNestedGenerated, 'utf8'), 'nested generated   ');
assert.equal(fs.readFileSync(fallbackEvalsResult, 'utf8'), 'eval result   ');

console.log('format-hard-eng: pass');
