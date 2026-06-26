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
assert.match(fail.stderr, new RegExp(`old /${String.fromCharCode(97, 97)} command`));
assert.match(fail.stderr, /old repo name/);

const denyTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'project-naming-deny-'));
fs.writeFileSync(path.join(denyTmp, 'private-denylist.txt'), 'secret-client\n');
fs.writeFileSync(path.join(denyTmp, 'notes.md'), 'This mentions Secret-Client in prose.\n');
const denyFail = spawnSync('node', [checker, denyTmp], { encoding: 'utf8' });
assert.notEqual(denyFail.status, 0);
assert.match(denyFail.stderr, /private-denylist\.txt:1/);

const invalidTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'project-naming-invalid-'));
fs.writeFileSync(path.join(invalidTmp, 'private-denylist.txt'), '[bad\n');
const invalidFail = spawnSync('node', [checker, invalidTmp], { encoding: 'utf8' });
assert.notEqual(invalidFail.status, 0);
assert.match(invalidFail.stderr, /invalid private denylist regex/);

console.log('project-naming-test: pass');
