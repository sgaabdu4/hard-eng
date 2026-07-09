#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'refresh-no-mistakes-agent-paths.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'no-mistakes-agent-paths-'));
const replacement = path.join(tmp, 'codex');
fs.writeFileSync(replacement, '#!/bin/sh\nexit 0\n', { mode: 0o755 });

function repair(name, text) {
  const config = path.join(tmp, `${name}.yaml`);
  fs.writeFileSync(config, text);
  const result = spawnSync('node', [script, '--config', config, '--agent', 'codex', '--binary', replacement], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return { config, output: result.stdout, text: fs.readFileSync(config, 'utf8') };
}

const stale = repair('stale', [
  'agent: codex',
  'agent_path_override:',
  '  codex: /missing/Codex.app/codex',
  '  claude: /custom/claude',
  'auto_fix:',
  '  review: 0',
  '',
].join('\n'));
assert.match(stale.output, /refreshed codex override/);
assert.match(stale.text, new RegExp(`  codex: ${JSON.stringify(replacement).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
assert.match(stale.text, /  claude: \/custom\/claude/);
assert.match(stale.text, /auto_fix:\n  review: 0/);

const validBinary = path.join(tmp, 'valid-codex');
fs.copyFileSync(replacement, validBinary);
fs.chmodSync(validBinary, 0o755);
const valid = repair('valid', `agent_path_override:\n  codex: ${validBinary}\n`);
assert.match(valid.output, /preserved executable codex override/);
assert.match(valid.text, new RegExp(validBinary.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));

const absent = repair('absent', 'agent: codex\nauto_fix:\n  review: 0\n');
assert.match(absent.output, /no override section/);
assert.equal(absent.text, 'agent: codex\nauto_fix:\n  review: 0\n');

console.log('no-mistakes-agent-paths-test: pass');
