#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.join(process.env.HOME, '.agents');
const finder = path.join(repo, 'scripts', 'find-deterministic-owner.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'deterministic-owner-'));

fs.mkdirSync(path.join(tmp, 'scripts'), { recursive: true });
fs.mkdirSync(path.join(tmp, 'tests'), { recursive: true });
fs.mkdirSync(path.join(tmp, '.github', 'workflows'), { recursive: true });
fs.mkdirSync(path.join(tmp, 'src'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'pnpm-lock.yaml'), '');
fs.writeFileSync(path.join(tmp, 'package.json'), JSON.stringify({
  scripts: {
    health: 'node scripts/check-health.mjs',
    test: 'node tests/health.test.mjs',
  },
}, null, 2));
fs.writeFileSync(path.join(tmp, 'scripts', 'check-health.mjs'), 'console.log("ok");\n');
fs.writeFileSync(path.join(tmp, 'tests', 'health.test.mjs'), 'console.log("pass");\n');
fs.writeFileSync(path.join(tmp, '.github', 'workflows', 'ci.yml'), 'name: ci\n');
fs.writeFileSync(path.join(tmp, 'src', 'health.ts'), 'export const health = true;\n');

const result = spawnSync(finder, ['--root', tmp, '--json', 'health check'], {
  encoding: 'utf8',
});
assert.equal(result.status, 0, result.stderr);
const parsed = JSON.parse(result.stdout);
const commands = parsed.candidates.map((candidate) => candidate.command);
const paths = parsed.candidates.map((candidate) => candidate.path);

assert.ok(commands.includes('pnpm run health'), 'must discover matching package scripts');
assert.ok(paths.includes('scripts/check-health.mjs'), 'must discover scripts');
assert.ok(paths.includes('tests/health.test.mjs'), 'must discover tests');
assert.ok(!paths.includes('src/health.ts'), 'must not treat product source as a deterministic owner');

const text = spawnSync(finder, ['--root', tmp, 'health'], { encoding: 'utf8' });
assert.equal(text.status, 0, text.stderr);
assert.match(text.stdout, /deterministic owners:/);
assert.match(text.stdout, /pnpm run health/);

console.log('deterministic-owner-test: pass');
