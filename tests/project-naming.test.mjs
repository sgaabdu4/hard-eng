import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.join(process.env.HOME, '.agents');
const checker = path.join(repo, 'scripts', 'check-project-naming.mjs');

const pass = spawnSync('node', [checker, repo], { encoding: 'utf8' });
assert.equal(pass.status, 0, pass.stderr);
assert.match(pass.stdout, /project-naming: pass/);

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'project-naming-'));
fs.writeFileSync(path.join(tmp, 'README.md'), `Run /a${'a'}:plan from ${String.fromCharCode(97, 98, 105, 100)}-agents.\n`);

const fail = spawnSync('node', [checker, tmp], { encoding: 'utf8' });
assert.notEqual(fail.status, 0);
assert.match(fail.stderr, new RegExp(`legacy /${String.fromCharCode(97, 97)} command`));
assert.match(fail.stderr, /legacy repo name/);

console.log('project-naming-test: pass');
