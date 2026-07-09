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
const outside = path.join(tmp, 'outside.md');
const owned = path.join(fixture, 'owned.md');
const link = path.join(fixture, 'link.md');

fs.mkdirSync(fixture, { recursive: true });
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: fixture, encoding: 'utf8' });
fs.writeFileSync(outside, 'external   \n');
fs.writeFileSync(owned, 'owned   ');
fs.symlinkSync(outside, link);

assert.equal(fs.lstatSync(link).isSymbolicLink(), true);

const result = spawnSync(process.execPath, [script, fixture], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.equal(fs.readFileSync(owned, 'utf8'), 'owned\n');
assert.equal(fs.readFileSync(outside, 'utf8'), 'external   \n');

console.log('format-hard-eng: pass');
